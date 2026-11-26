"""DP 1.22 historical analogues hc-0.1 (AC-38; D-38; DC §3.4a). SYNTHETIC cases."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest

from sr.events.analogues import AnalogueCase, AnalogueQuery, find_analogues, load_cases, surprise_bucket
from sr.events.merge import EvidenceIn, attach_evidence
from sr.events.versions import publish_analysis
from sr.evidence.ingest import ingest
from sr.evidence.sources.base import RawDocument

ASOF = datetime(2026, 11, 19, 21, 30, tzinfo=UTC)
Q = AnalogueQuery(
    event_id="evt_now",
    chain_key="earnings:co_nvda:FY2027Q3",
    company_id="co_nvda",
    industry_template="semiconductor",
    sector="Information Technology",
    event_type="earnings_guidance",
    subtype="quarterly_results",
    market_state="post_market",
    surprise_bucket="above",
    target_id="next_regular_session",
    analysis_as_of=ASOF,
)


def case(i: int, pp: float, **kw: Any) -> AnalogueCase:
    base = dict(
        case_id=f"eav_c{i:02d}",
        event_id=f"evt_c{i:02d}",
        chain_key=f"earnings:co_nvda:FY20{10 + i}Q3",
        company_id="co_nvda",
        industry_template="semiconductor",
        sector="Information Technology",
        event_type="earnings_guidance",
        subtype="quarterly_results",
        market_state="post_market",
        surprise_bucket="above",
        available_at=ASOF - timedelta(days=90 * (i + 1)),
        settled_at=ASOF - timedelta(days=90 * (i + 1) - 1),
        outcomes={"next_regular_session": pp},
    )
    return AnalogueCase(**(base | kw))  # type: ignore[arg-type]


PPS = [1.2, -0.4, 2.5, 0.8, 3.1, -1.6, 0.3, 1.9, 0.6]


def test_enough_exact_cases_no_fallback() -> None:
    out = find_analogues(Q, [case(i, pp) for i, pp in enumerate(PPS)])
    v = np.array(PPS)
    assert (
        out["n"] == 9
        and out["fallback_level"] == "none"
        and not out["fallback_applied"]
        and not out["insufficient"]
    )
    assert out["median_relative_pp"] == pytest.approx(float(np.median(v)))
    assert out["iqr_pp"] == pytest.approx(float(np.percentile(v, 75) - np.percentile(v, 25)))
    assert out["hit_share_positive"] == pytest.approx(7 / 9)
    assert out["case_ids"] == sorted(out["case_ids"]) and out["period"]["start"] < out["period"]["end"]
    assert out["match_keys"]["surprise_bucket"] == "above" and out["query_version"] == "hc-0.1"


def test_five_exact_relaxes_to_drop_subtype() -> None:
    cases = [case(i, pp) for i, pp in enumerate(PPS[:5])] + [
        case(10 + i, pp, subtype="guidance_update") for i, pp in enumerate(PPS[5:])
    ]
    out = find_analogues(Q, cases)
    assert out["fallback_level"] == "drop_subtype" and out["n"] == 9 and out["fallback_applied"]


def test_relaxes_to_peer_group_then_sector() -> None:
    peers = [case(20 + i, pp, company_id="co_amd") for i, pp in enumerate(PPS)]
    assert find_analogues(Q, peers)["fallback_level"] == "peer_group"
    sector = [
        case(
            30 + i,
            pp,
            company_id="co_aapl",
            industry_template="generic",
            market_state="regular",
            surprise_bucket="below",
        )
        for i, pp in enumerate(PPS)
    ]
    assert find_analogues(Q, sector)["fallback_level"] == "sector_wide"


def test_still_insufficient_shows_no_statistics() -> None:
    out = find_analogues(Q, [case(i, pp) for i, pp in enumerate(PPS[:5])])
    assert out["insufficient"] and out["fallback_level"] == "sector_wide" and out["n"] == 5
    assert out["median_relative_pp"] is None and out["iqr_pp"] is None and out["hit_share_positive"] is None


def test_negative_future_and_self_matches_excluded() -> None:
    good = [case(i, pp) for i, pp in enumerate(PPS[:8])]
    bad = [
        case(50, 9.0, available_at=ASOF + timedelta(minutes=1)),  # not yet available
        case(51, 9.0, settled_at=ASOF + timedelta(hours=1)),  # outcome not yet known
        case(52, 9.0, event_id="evt_now"),  # the event itself
        case(53, 9.0, chain_key=Q.chain_key),  # same chain (revision/repost)
        case(54, 9.0, outcomes={"regular_60m": 9.0}),  # other target window
    ]
    out = find_analogues(Q, good + bad)
    assert out["n"] == 8 and not any(cid.startswith("eav_c5") for cid in out["case_ids"])
    assert out["median_relative_pp"] == pytest.approx(float(np.median(PPS[:8])))


def test_surprise_bucket_only_for_earnings() -> None:
    below = [case(i, pp, surprise_bucket="below") for i, pp in enumerate(PPS)]
    assert find_analogues(Q, below)["fallback_level"] == "sector_wide"  # above != below until sector level
    policy_q = replace(
        Q, event_type="policy_export", subtype=None, chain_key="policy:BIS:x", surprise_bucket=None
    )
    policy = [
        case(
            i, pp, event_type="policy_export", subtype=None, surprise_bucket=None, chain_key=f"policy:BIS:{i}"
        )
        for i, pp in enumerate(PPS)
    ]
    out = find_analogues(policy_q, policy)
    assert out["fallback_level"] == "none" and "surprise_bucket" not in out["match_keys"]


def test_surprise_bucket_from_comparison() -> None:
    assert surprise_bucket({"difference_pct": 8.0}) == "above"
    assert surprise_bucket({"difference_pct": -0.5}) == "in_line"
    assert surprise_bucket({"difference_pp": -1.1}) == "below"
    assert surprise_bucket(None) is None and surprise_bucket({}) is None


def test_deterministic() -> None:
    cases = [case(i, pp) for i, pp in enumerate(PPS)]
    assert find_analogues(Q, cases) == find_analogues(Q, list(reversed(cases)))


# ---------------------------------------------------------------- point-in-time loader (Postgres)
def _publish(conn, storage, n: int, company_sec: str, published: datetime, settled: datetime) -> None:  # type: ignore[no-untyped-def]
    r = ingest(
        conn,
        RawDocument(
            source_id="src_sec_edgar",
            external_ref=f"acc-{n}",
            title="8-K (synthetic)",
            content=f"synthetic results {n}".encode(),
            content_type="text/plain",
            received_at=published - timedelta(minutes=5),
            source_published_at=published - timedelta(minutes=6),
            source_published_precision="s",
        ),
        now=published - timedelta(minutes=4),
        storage=storage,
    )
    m = attach_evidence(
        conn,
        f"earnings:co_x{n}:FY2026Q{1 + n % 4}",
        "earnings_guidance",
        EvidenceIn(r.doc_version_id, f"c{n}", {}, "primary_confirmed", f"o{n}"),
        now=published,
    )
    payload = {
        "analysis_kind": "full",
        "prediction_readiness": {},
        "market_explanation": {"status": "partial"},
        "expectation_comparison": {"metric": "eps_non_gaap", "difference_pct": 5.0},
        "market_reaction": {
            "market_state": "post_market",
            "settled_at": settled.isoformat(),
            "outcomes": {"next_regular_session": 0.5 * n},
        },
    }
    publish_analysis(
        conn, m.event_id, company_sec, published - timedelta(minutes=1), lambda s: payload, published
    )


def test_load_cases_point_in_time(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    _publish(conn, doc_storage, 1, "sec_nvda", ASOF - timedelta(days=30), ASOF - timedelta(days=29))
    _publish(conn, doc_storage, 2, "sec_qcom", ASOF - timedelta(days=20), ASOF - timedelta(days=19))
    _publish(
        conn, doc_storage, 3, "sec_nvda", ASOF + timedelta(minutes=5), ASOF + timedelta(days=1)
    )  # future case
    _publish(
        conn, doc_storage, 4, "sec_nvda", ASOF - timedelta(hours=2), ASOF + timedelta(hours=10)
    )  # unsettled
    cases = {c.chain_key: c for c in load_cases(conn, ASOF)}
    assert set(cases) == {"earnings:co_x1:FY2026Q2", "earnings:co_x2:FY2026Q3"}
    nv, qc = cases["earnings:co_x1:FY2026Q2"], cases["earnings:co_x2:FY2026Q3"]
    assert (
        nv.industry_template == "semiconductor"
        and nv.company_id == "co_nvda"
        and nv.surprise_bucket == "above"
    )
    assert nv.template_retroactive  # profile dated 2026-11-26, applied retroactively
    assert (
        qc.industry_template == "generic" and not qc.template_retroactive
    )  # no profile for peer_only companies
    assert nv.outcomes == {"next_regular_session": 0.5} and nv.market_state == "post_market"
