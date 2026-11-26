"""DP 1.07 earnings + DP 1.08 policy templates end to end on Postgres (AC-09; AC-12 hand-off). SYNTHETIC data."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from sr.events.earnings import process_earnings_document
from sr.events.policy import process_policy_document
from sr.evidence.hashing import normalized_text
from sr.evidence.ingest import ingest, ingest_all
from sr.evidence.sources.base import RawDocument
from sr.evidence.sources.federal_register import FederalRegisterSource
from sr.evidence.sources.transport import ArchiveTransport
from sr.llm.fake import FakeLLMProvider
from sr.timeguard import LookaheadError
from tests.conftest import EVIDENCE_ARCHIVE

EX991 = EVIDENCE_ARCHIVE / "www.sec.gov/Archives/edgar/data/9999001/000999900126000201/ex991.htm"
DISCLOSED = datetime(2026, 11, 19, 21, 20, 31, tzinfo=UTC)
AVAILABLE = datetime(2026, 11, 19, 21, 21, 5, tzinfo=UTC)
ASOF = AVAILABLE + timedelta(minutes=1)


def ingest_release(conn, storage) -> str:  # type: ignore[no-untyped-def]
    raw = RawDocument(
        source_id="src_sec_edgar",
        external_ref="0009999001-26-000201",
        title="EX-99.1 (synthetic)",
        content=EX991.read_bytes(),
        content_type="text/html",
        received_at=datetime(2026, 11, 19, 21, 20, 45, tzinfo=UTC),
        arrival_mode="archived",
        available_at=AVAILABLE,
        source_published_at=DISCLOSED,
        source_published_precision="s",
        subject_company_ids=("co_nvda",),
    )
    return ingest(conn, raw, storage=storage).doc_version_id


LLM_FACTS = [  # what a correct structured extraction looks like (fake provider replays it)
    {
        "metric": "revenue",
        "value": 35.1,
        "unit": "USD_billion",
        "currency": "USD",
        "period": "third quarter of fiscal 2027",
        "basis": None,
        "quote": "Revenue for the quarter was $35.1 billion",
    },
    {
        "metric": "earnings per diluted share",
        "value": 0.79,
        "unit": "USD_per_share",
        "currency": "USD",
        "period": None,
        "basis": "gaap",
        "quote": "GAAP earnings per diluted share for the quarter were $0.79",
    },
    {
        "metric": "earnings per diluted share",
        "value": 0.81,
        "unit": "USD_per_share",
        "currency": "USD",
        "period": None,
        "basis": "non_gaap",
        "quote": "Non-GAAP earnings per diluted share for the quarter were $0.81",
    },
    {
        "metric": "gross margin",
        "value": 74.6,
        "unit": "pct",
        "currency": None,
        "period": None,
        "basis": "gaap",
        "quote": "GAAP gross margin was 74.6%",
    },
    {
        "metric": "revenue outlook",
        "value": 37.5,
        "unit": "USD_billion",
        "currency": "USD",
        "period": "fourth quarter of fiscal 2027",
        "basis": None,
        "quote": "Revenue is expected to be $37.5 billion",
    },
]


def provider(facts: list[dict[str, Any]] = LLM_FACTS) -> FakeLLMProvider:
    p = FakeLLMProvider()
    p.register(normalized_text(EX991.read_bytes(), "text/html"), facts)
    return p


def consensus(value: float, as_of: datetime) -> dict[str, Any]:
    z = as_of.isoformat().replace("+00:00", "Z")
    return {
        "exp_id": f"exp_{value}",
        "company_id": "co_nvda",
        "metric": "eps_non_gaap",
        "fiscal_period": "FY2027Q3",
        "value": value,
        "unit": "USD_per_share",
        "accounting_basis": "non_gaap",
        "expectation_type": "analyst_consensus",
        "snapshot_as_of": z,
        "snapshot_precision": "s",
        "available_at": z,
        "source_id": "src_synthetic",
    }


def run(conn, storage, snaps, facts=LLM_FACTS, asof=ASOF):  # type: ignore[no-untyped-def]
    dv = ingest_release(conn, storage)
    return process_earnings_document(
        conn, dv, "co_nvda", "sec_nvda", "FY2027Q3", provider(facts), snaps, asof, asof, storage=storage
    )


def test_ac09_separate_eps_and_post_event_consensus(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    out = run(
        conn, doc_storage, [consensus(0.80, DISCLOSED + timedelta(minutes=2))]
    )  # only snapshot is AFTER release
    by = {f["metric"]: f for f in out.facts}
    assert set(by) == {"revenue", "eps_gaap", "eps_non_gaap", "gross_margin_pct", "revenue_outlook"}
    assert by["eps_gaap"]["value"] == 0.79 and by["eps_non_gaap"]["value"] == 0.81  # separate fields
    assert by["revenue"]["value"] == pytest.approx(35.1e9) and by["revenue_outlook"]["period"] == "FY2027Q4"
    assert out.expectation_comparison is None and out.missing_reason == "no_pre_event_consensus"
    row = conn.execute("select * from event_analysis_versions").fetchone()
    assert row["expectation_comparison"] is None and row["missing_reason"] == "no_pre_event_consensus"
    assert row["prediction_readiness"]["stock_reaction"] == {
        "status": "missing_inputs",
        "reason": "market_data_pending",
        "allowed_models": ["market_baseline"],
    }
    ev = conn.execute("select * from events").fetchone()
    assert ev["identity_key"] == "earnings:co_nvda:FY2027Q3" and ev["evidence_status"] == "primary_confirmed"
    assert len(row["evidence_ids"]) == 5
    for st in row["market_explanation"]["observed_facts"]:
        assert st["evidence_ids"]  # D-46 citations


def test_pre_event_consensus_difference(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    out = run(conn, doc_storage, [consensus(0.75, DISCLOSED - timedelta(hours=3))])
    assert out.expectation_comparison is not None and out.missing_reason is None
    assert out.expectation_comparison["metric"] == "eps_non_gaap"
    assert out.expectation_comparison["difference_pct"] == pytest.approx(8.0)


def test_bad_fact_goes_to_review_but_good_ones_publish(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    facts = [*LLM_FACTS[:2], {**LLM_FACTS[2], "value": 0.18}]  # LLM misread $0.81 as 0.18
    out = run(conn, doc_storage, [], facts)
    assert out.analysis_status == "needs_review" and any("value_not_in_quote" in g for g in out.data_gaps)
    assert {f["metric"] for f in out.facts} == {"revenue", "eps_gaap"}
    assert conn.execute("select analysis_status from events").fetchone()["analysis_status"] == "needs_review"


def test_unverifiable_extraction_creates_nothing(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    facts = [{**LLM_FACTS[0], "quote": "Revenue was a record $40 billion"}]
    out = run(conn, doc_storage, [], facts)
    assert out.event_id is None and out.data_gaps == ["extraction_rejected_validation"]
    assert conn.execute("select count(*) n from events").fetchone()["n"] == 0


def test_earnings_replay_cannot_read_ahead(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(LookaheadError):
        run(conn, doc_storage, [], asof=AVAILABLE - timedelta(seconds=1))


# ---------------------------------------------------------------- policy (DP 1.08)
POLICY_ASOF = datetime(2026, 12, 4, 14, 0, tzinfo=UTC)


@pytest.fixture
def fr_versions(conn, doc_storage) -> dict[str, str]:  # type: ignore[no-untyped-def]
    docs = FederalRegisterSource(ArchiveTransport(EVIDENCE_ARCHIVE)).poll(datetime(2026, 12, 1, tzinfo=UTC))
    assert all(d.source_published_precision == "day" for d in docs)
    res = ingest_all(conn, docs, storage=doc_storage)
    return {d.external_ref: r.doc_version_id for d, r in zip(docs, res, strict=True)}


def test_policy_rule_advanced_computing(conn, doc_storage, fr_versions) -> None:  # type: ignore[no-untyped-def]
    out = process_policy_document(
        conn, fr_versions["2026-91234"], POLICY_ASOF, POLICY_ASOF, storage=doc_storage
    )
    assert out.template == "bis_export_control" and out.topics == ["advanced_computing"]
    assert {(lk.security_id, lk.relation) for lk in out.links} == {
        ("sec_nvda", "regulated_party"),
        ("sec_amd", "regulated_party"),
        ("sec_avgo", "sector_wide"),
        ("sec_mu", "sector_wide"),
    }
    ev = conn.execute("select * from events where event_id = %s", (out.event_id,)).fetchone()
    assert ev["identity_key"] == "policy:BIS:2026-91234" and ev["category"] == "policy_export"
    assert ev["evidence_status"] == "primary_confirmed" and ev["progress_status"] == "effective"
    ms = {m["type"]: m for m in out.milestones}
    assert set(ms) == {"rule_published", "rule_effective"} and ms["rule_effective"]["occurred"]
    rows = conn.execute(
        "select security_id, prediction_readiness, impact from event_analysis_versions"
    ).fetchall()
    assert len(rows) == 4
    for (
        r
    ) in rows:  # AC-12 hand-off: event-enhanced model not validated for policy_export -> market baseline only
        assert r["prediction_readiness"]["stock_reaction"]["allowed_models"] == ["market_baseline"]
        assert r["impact"][0]["direction"] == "unknown"
    # idempotent re-run: no duplicate milestones, analyses with the same input watermark are discarded
    again = process_policy_document(
        conn, fr_versions["2026-91234"], POLICY_ASOF, POLICY_ASOF, storage=doc_storage
    )
    assert not any(m["created"] for m in again.milestones)
    assert all(p.status == "discarded" for p in again.published)
    assert conn.execute("select count(*) n from event_milestones").fetchone()["n"] == 2


def test_policy_proposed_rule_hbm(conn, doc_storage, fr_versions) -> None:  # type: ignore[no-untyped-def]
    out = process_policy_document(
        conn, fr_versions["2026-91300"], POLICY_ASOF, POLICY_ASOF, storage=doc_storage
    )
    assert out.topics == ["high_bandwidth_memory"] and out.progress_status is None
    ms = {m["type"]: m for m in out.milestones}
    assert ms["proposed_rule"]["occurred"] and not ms["comment_period_end"]["occurred"]
    st = conn.execute(
        "select status from event_milestones where milestone_type = 'comment_period_end'"
    ).fetchone()
    assert st["status"] == "scheduled"
    rel = {lk.security_id: lk.relation for lk in out.links}
    assert rel == {"sec_mu": "regulated_party", "sec_nvda": "customer"}


def test_policy_without_topic_needs_review(conn, doc_storage, fr_versions) -> None:  # type: ignore[no-untyped-def]
    out = process_policy_document(
        conn, fr_versions["2026-91411"], POLICY_ASOF, POLICY_ASOF, storage=doc_storage
    )
    assert out.links == [] and "no_exposure_topic_matched" in out.data_gaps and out.published == []
    ms = {m["type"]: m for m in out.milestones}
    assert not ms["rule_effective"]["occurred"]  # effective 2026-12-20 > as_of
    assert (
        conn.execute("select progress_status from events where event_id = %s", (out.event_id,)).fetchone()[
            "progress_status"
        ]
        == "pending"
    )
