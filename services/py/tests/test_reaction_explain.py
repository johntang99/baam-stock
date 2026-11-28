"""DP 1.09 market reaction + current explanation + time-order check (AC-10, AC-40, AC-57; OQ-43). SYNTHETIC data."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import pytest

from sr.events.explain import anchor_at, basket_for, publish_explanation
from sr.events.reaction import compute_reaction, quote_id
from sr.events.reasoning import EvidenceInfo, build
from sr.events.versions import publish_analysis
from sr.marketdata.quote_rules import evaluate_quotes
from sr.timeguard import LookaheadError

# 2026-12-02 is EST: 15:00Z = 10:00 ET (regular session)
T0 = datetime(2026, 12, 2, 15, 0, tzinfo=UTC)
NVDA, PEERS = "sec_nvda", ["sec_amd", "sec_avgo", "sec_mu"]
W = {p: 1 / 3 for p in PEERS}


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def ramp(p0: float, p1: float, start: datetime, end: datetime) -> Callable[[datetime], float]:
    """Flat p0 until start, linear to p1 at end, flat p1 after (synthetic)."""

    def f(t: datetime) -> float:
        if t <= start:
            return p0
        if t >= end:
            return p1
        return p0 + (p1 - p0) * (t - start) / (end - start)

    return f


def make_quotes(
    paths: dict[str, Callable[[datetime], float]], start: datetime, end: datetime
) -> pd.DataFrame:
    rows = []
    t = start
    while t <= end:
        for sid, f in paths.items():
            m = f(t)
            rows.append(
                {
                    "ts": t,
                    "security_id": sid,
                    "quote_ts": t,
                    "received_at": t + timedelta(milliseconds=200),
                    "bid": m - 0.005,
                    "ask": m + 0.005,
                    "last": m,
                    "halted": False,
                    "luld_pause": False,
                }
            )
        t += timedelta(seconds=1)
    df = pd.DataFrame(rows)
    for c in ("ts", "quote_ts", "received_at"):
        df[c] = pd.to_datetime(df[c], utc=True)
    return evaluate_quotes(df)


def visible(q: pd.DataFrame, as_of: datetime) -> pd.DataFrame:
    """Only quotes already received at as_of (what a point-in-time caller passes in)."""
    return q[q["received_at"] <= pd.Timestamp(as_of)].reset_index(drop=True)


def scenario_quotes(
    stock: Callable[[datetime], float], peer: Callable[[datetime], float], end: datetime
) -> pd.DataFrame:
    return visible(make_quotes({NVDA: stock, **{p: peer for p in PEERS}}, at(-25), end), end)


# ---------------------------------------------------------------- AC-10 returns
def test_ac10_absolute_and_relative_returns() -> None:
    # news 10:49:30 ET (15:49:30Z); stock -1%, basket -3% between 15:50Z and 16:00Z
    asof = at(60.5)
    q = scenario_quotes(ramp(100, 99, at(50), at(60)), ramp(100, 97, at(50), at(60)), asof)
    r = compute_reaction(q, NVDA, PEERS, at(49.5), asof, W)
    mr = r.market_reaction
    assert mr["stock_return_pct"] == pytest.approx(-1.0, abs=1e-6)
    assert mr["benchmark_return_pct"] == pytest.approx(-3.0, abs=1e-6)
    assert mr["relative_return_pp"] == pytest.approx(2.0, abs=1e-6)  # displayed: absolute -1%, relative +2pp
    assert mr["missing_reason"] is None
    # ref_before = last sync point strictly before the evidence; ref_asof = last at/before as_of
    assert mr["ref_before_quote_id"] == quote_id(NVDA, pd.Timestamp(at(49.5) - timedelta(seconds=1)))
    assert (
        mr["ref_asof_quote_id"] == "rq_nvda_20261202_160029"
    )  # 16:00:30 arrives 200 ms after as_of (as in DC §8)
    assert set(mr) == {
        "ref_before_quote_id",
        "ref_asof_quote_id",
        "stock_return_pct",
        "benchmark_return_pct",
        "relative_return_pp",
        "missing_reason",
    }  # DC fields exactly
    # stored rows: the two stock quotes + every constituent quote used at both points
    assert len(r.quote_rows) == 2 + 2 * len(PEERS)
    assert {x["session_type"] for x in r.quote_rows} == {"regular"}


def test_move_start_is_the_extreme_before_the_move() -> None:
    # relative fall starts at 15:40Z; the basket is flat
    asof = at(60)
    q = scenario_quotes(ramp(100, 98, at(40), at(58)), ramp(100, 100, at(0), at(1)), asof)
    r = compute_reaction(q, NVDA, PEERS, at(55), asof, W)
    assert r.move is not None and r.detail["material_move"] is True
    assert abs(r.move.move_start_at - at(40)) <= timedelta(seconds=10)  # path sampled every 10 s


def test_no_material_move_falls_back_to_ref_before() -> None:
    asof = at(60)
    q = scenario_quotes(ramp(100, 100.1, at(40), at(58)), ramp(100, 100, at(0), at(1)), asof)  # +0.1pp
    r = compute_reaction(q, NVDA, PEERS, at(55), asof, W)
    assert r.detail["material_move"] is False
    assert r.move is not None and r.move.move_start_at == at(55) - timedelta(seconds=1)


# ---------------------------------------------------------------- AC-40 basket unavailable
def test_ac40_basket_unavailable_keeps_absolute_return() -> None:
    asof = at(60)
    q = visible(
        make_quotes(
            {NVDA: ramp(100, 102, at(50), at(58)), "sec_amd": ramp(100, 100, at(0), at(1))}, at(-25), asof
        ),
        asof,
    )
    r = compute_reaction(q, NVDA, PEERS, at(49), asof, W)  # 2 of 3 constituents have no quotes (> 1 missing)
    mr = r.market_reaction
    assert mr["stock_return_pct"] == pytest.approx(2.0, abs=1e-6)
    assert mr["benchmark_return_pct"] is None and mr["relative_return_pp"] is None
    assert mr["missing_reason"] == "benchmark_unavailable"
    assert r.move is not None and r.move.benchmark_return_pct is None


def test_no_stock_quote() -> None:
    asof = at(60)
    q = visible(make_quotes({p: ramp(100, 100, at(0), at(1)) for p in PEERS}, at(-25), asof), asof)
    r = compute_reaction(q, NVDA, PEERS, at(49), asof, W)
    assert r.move is None and r.market_reaction["missing_reason"] == "no_qualifying_quote"


def test_wide_spread_quotes_do_not_count() -> None:
    asof = at(60)
    q = scenario_quotes(ramp(100, 99, at(50), at(55)), ramp(100, 100, at(0), at(1)), asof)
    late = (q["security_id"] == NVDA) & (q["ts"] > pd.Timestamp(at(59)))
    q.loc[late, "is_qualifying"] = False  # e.g. wide spread in the last minute
    r = compute_reaction(q, NVDA, PEERS, at(49), asof, W)
    assert r.market_reaction["missing_reason"] == "no_qualifying_quote"  # no sync point within 30 s of as_of


# ---------------------------------------------------------------- point in time (negative tests)
def test_quotes_received_after_as_of_raise() -> None:
    asof = at(60)
    q = make_quotes(
        {NVDA: ramp(100, 99, at(50), at(55)), **{p: ramp(100, 100, at(0), at(1)) for p in PEERS}},
        at(-25),
        at(61),
    )
    with pytest.raises(LookaheadError):
        compute_reaction(q, NVDA, PEERS, at(49), asof, W)


def test_anchor_after_as_of_is_refused() -> None:
    q = scenario_quotes(ramp(100, 99, at(50), at(55)), ramp(100, 100, at(0), at(1)), at(60))
    with pytest.raises(ValueError):
        compute_reaction(q, NVDA, PEERS, at(61), at(60), W)


# ---------------------------------------------------------------- AC-10 / AC-57 time order (no DB)
class AllExist:
    def missing(self, kind: str, ids: list[str]) -> set[str]:
        return set()


def test_ac10_news_later_than_drop_is_not_its_cause() -> None:
    # the drop starts 15:40Z; the news comes out at 15:55Z, i.e. after the drop began
    asof = at(60)
    q = scenario_quotes(ramp(100, 98, at(40), at(58)), ramp(100, 100, at(0), at(1)), asof)
    news = EvidenceInfo("evd_late", "Export rule report (synthetic)", at(55), "s", at(55), "media_report")
    r = compute_reaction(q, NVDA, PEERS, anchor_at([news]), asof, W)
    driver = {"text": "出口规则导致下跌", "evidence_ids": ["evd_late"], "quote_ids": [], "item_ids": []}
    expl, trace, _ = build(r.move, [news], [driver], [], AllExist())
    assert expl["possible_drivers"] == []
    assert [d["text"] for d in expl["concurrent_events"]] == ["出口规则导致下跌"]
    timing = [s for s in trace if s["kind"] == "timing_check"]
    assert timing and "不能作为此前走势的原因" in timing[0]["conclusion"]
    # an earlier piece of evidence may be a cause
    early = EvidenceInfo("evd_early", "Rule published (synthetic)", at(35), "s", at(35), "primary_confirmed")
    d2 = {"text": "规则公布", "evidence_ids": ["evd_early"], "quote_ids": [], "item_ids": []}
    expl2, _, _ = build(r.move, [early], [d2], [], AllExist())
    assert [d["text"] for d in expl2["possible_drivers"]] == ["规则公布"]


def test_anchor_uses_precise_public_time_else_availability() -> None:
    precise = EvidenceInfo("a", "c", at(10), "s", at(12), "primary_confirmed")
    day_only = EvidenceInfo("b", "c", at(-600), "day", at(5), "primary_confirmed")
    assert anchor_at([precise, day_only]) == at(5)
    with pytest.raises(ValueError):
        anchor_at([])


def test_basket_excludes_target() -> None:
    b = basket_for("sec_nvda")
    assert "sec_nvda" not in b and "sec_amd" in b and len(b) == 11


# ---------------------------------------------------------------- end to end on the database
def test_publish_explanation_appends_a_version(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    from sr.events.merge import EvidenceIn, attach_evidence
    from sr.evidence.collection_log import run_collection
    from tests.test_collection_reasoning import ASOF, WINDOW, scenario

    sources, _ = scenario(conn)  # the flash is published 15:59:50Z (precision s), available 16:00:10Z
    res = run_collection(conn, "sec_nvda", sources, WINDOW, ASOF, storage=doc_storage, now=ASOF)
    item = conn.execute(
        "select * from collection_items where collection_run_id = %s and disposition = 'kept' "
        "and channel = 'news_wire' order by available_at limit 1",
        (res.collection_run_id,),
    ).fetchone()
    m = attach_evidence(
        conn,
        "policy:BIS:demo-2026-12345",
        "policy_export",
        EvidenceIn(
            item["doc_version_id"], "BIS export license rule (synthetic)", {}, "primary_confirmed", "o:1"
        ),
        now=ASOF,
    )
    first_as_of = datetime(2026, 12, 2, 16, 1, tzinfo=UTC)
    placeholder: dict[str, Any] = {
        "analysis_kind": "flash",
        "evidence_ids": [m.evidence_id],
        "data_gaps": ["market_reaction_pending"],
        "market_reaction": {"missing_reason": "market_data_pending"},
        "market_explanation": {
            "status": "insufficient",
            "observed_facts": [
                {
                    "text": "规则公布（虚构）",
                    "evidence_ids": [m.evidence_id],
                    "quote_ids": [],
                    "item_ids": [],
                    "trace_step": 1,
                }
            ],
            "possible_drivers": [],
            "counter_evidence": [],
            "unexplained": ["市场反应待行情数据"],
            "concurrent_events": [],
        },
        "prediction_readiness": {"event_outcome": {"status": "manual_review", "reason": "x"}},
    }
    v1 = publish_analysis(conn, m.event_id, NVDA, first_as_of, lambda s: placeholder, first_as_of)
    assert v1.status == "published"

    # NVDA starts falling relative to peers at 15:45Z, before the 15:59:50Z publication
    asof = ASOF  # 16:30Z
    q = make_quotes(
        {
            NVDA: ramp(
                100, 98, datetime(2026, 12, 2, 15, 45, tzinfo=UTC), datetime(2026, 12, 2, 16, 20, tzinfo=UTC)
            ),
            **{p: ramp(100, 100, at(0), at(1)) for p in PEERS},
        },
        datetime(2026, 12, 2, 15, 0, tzinfo=UTC),
        asof,
    )
    q = q[q["received_at"] <= asof].reset_index(drop=True)
    driver = {
        "text": "出口规则导致下跌（虚构）",
        "evidence_ids": [m.evidence_id],
        "quote_ids": [],
        "item_ids": [],
    }
    out = publish_explanation(conn, m.event_id, NVDA, asof, asof, q, drafted_drivers=[driver], weights=W)
    assert out.publish.status == "published" and out.publish.analysis_version == 2

    row = conn.execute(
        "select * from event_analysis_versions where analysis_id = %s", (out.publish.analysis_id,)
    ).fetchone()
    assert row["supersedes_analysis_id"] == v1.analysis_id
    mr = row["market_reaction"]
    assert mr["relative_return_pp"] is not None and mr["relative_return_pp"] < 0
    # cited quotes were stored, so citations resolve
    ids = [mr["ref_before_quote_id"], mr["ref_asof_quote_id"]]
    assert (
        len(conn.execute("select 1 from reference_quotes where quote_id = any(%s)", (ids,)).fetchall()) == 2
    )
    ex = row["market_explanation"]
    assert ex["possible_drivers"] == []  # the publication came after the drop began (AC-10)
    assert [d["text"] for d in ex["concurrent_events"]] == ["出口规则导致下跌（虚构）"]
    assert any(f["text"] == "规则公布（虚构）" for f in ex["observed_facts"])  # carried over, re-pointed
    assert "market_reaction_pending" not in row["data_gaps"]
    assert row["prediction_readiness"]["stock_reaction"]["status"] == "ready"
    assert row["prediction_readiness"]["event_outcome"]["reason"] == "x"  # untouched
    assert row["reasoning_trace"][0]["kind"] == "market_fact"
    # version 1 is still there, unchanged (append-only)
    old = conn.execute(
        "select market_reaction from event_analysis_versions where analysis_id = %s", (v1.analysis_id,)
    ).fetchone()
    assert old["market_reaction"] == {"missing_reason": "market_data_pending"}


# ---------------------------------------------------------------- the synthetic 1-second fixture (Phase 0)
def test_reaction_on_the_synthetic_fixture(fixture_path, basket_ex_nvda) -> None:  # type: ignore[no-untyped-def]
    from sr.events.explain import quotes_for
    from sr.marketdata.providers.fixture import FixtureProvider

    asof = datetime(2026, 12, 1, 17, 0, tzinfo=UTC)  # 12:00 ET
    anchor = datetime(2026, 12, 1, 16, 30, tzinfo=UTC)
    q = quotes_for(FixtureProvider(fixture_path, as_of=asof), NVDA, basket_ex_nvda, asof, anchor)
    r = compute_reaction(q, NVDA, basket_ex_nvda, anchor, asof)
    mr = r.market_reaction
    assert mr["stock_return_pct"] is not None and mr["ref_asof_quote_id"].startswith("rq_nvda_20261201_16")
    assert (mr["relative_return_pp"] is None) == (mr["missing_reason"] == "benchmark_unavailable")
    # the provider refuses to serve anything after its own as_of (negative test)
    with pytest.raises(LookaheadError):
        quotes_for(
            FixtureProvider(fixture_path, as_of=asof - timedelta(minutes=1)),
            NVDA,
            basket_ex_nvda,
            asof,
            anchor,
        )
