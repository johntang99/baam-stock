"""AC-39 earnings at 16:20 ET + post-market +8%, AC-40 post-market basket missing (DP 1.25; D-10, D-28; OQ-55).
SYNTHETIC data."""

from datetime import date, time, timedelta
from pathlib import Path

import pytest

from sr.calendar.calendar import et_to_utc
from sr.calendar.windows import next_session_start_bound
from sr.events.explain import publish_explanation
from sr.events.merge import EvidenceIn, Link, attach_evidence
from sr.evidence.ingest import ingest
from sr.forecast.run import forecast_snapshot
from sr.snapshot.builder import build_snapshot
from sr.snapshot.triggers import detect_market_move
from tests.test_collection_reasoning import doc
from tests.test_dataset import FrameProvider
from tests.test_reaction_explain import make_quotes, ramp, visible

D = date(2026, 12, 2)  # Wednesday; close 16:00 ET = 21:00Z
NVDA = "sec_nvda"
PEERS = ["sec_amd", "sec_avgo", "sec_mu"]
W = {p: 1 / 3 for p in PEERS}
RELEASE = et_to_utc(D, time(16, 20))
ASOF = et_to_utc(D, time(16, 40))


def post_market_quotes(peers_after_close: bool):  # type: ignore[no-untyped-def]
    """NVDA 100 into the close, then to 108 by 16:35 ET; peers 50 flat (and quoting after the close, or not)."""
    start, close = et_to_utc(D, time(15, 30)), et_to_utc(D, time(16, 0))
    q = make_quotes(
        {NVDA: ramp(100, 108, RELEASE + timedelta(seconds=30), et_to_utc(D, time(16, 35)))}, start, ASOF
    )
    peer_end = ASOF if peers_after_close else close - timedelta(seconds=1)
    qp = make_quotes({p: ramp(50, 50, start, start + timedelta(seconds=1)) for p in PEERS}, start, peer_end)
    import pandas as pd

    return visible(pd.concat([q, qp], ignore_index=True), ASOF)


def earnings_event(conn, storage) -> str:  # type: ignore[no-untyped-def]
    raw = doc(
        "src_sec_edgar",
        "8k-earn-demo",
        "NVIDIA reports quarterly results (synthetic). Revenue rose.",
        RELEASE + timedelta(seconds=40),
        published=RELEASE,
        subjects=("co_nvda",),
    )
    r = ingest(conn, raw, now=RELEASE + timedelta(seconds=40), storage=storage)
    m = attach_evidence(
        conn,
        "earnings:co_nvda:FY2027Q3-demo",
        "earnings_guidance",
        EvidenceIn(
            r.doc_version_id, "Quarterly results released (synthetic)", {}, "primary_confirmed", "8k-earn"
        ),
        links=[Link(NVDA, "subject")],
        now=RELEASE + timedelta(minutes=1),
    )
    return m.event_id


@pytest.mark.parametrize("peers_after_close", [True, False])
def test_ac39_ac40_post_market_move(conn, doc_storage, tmp_path: Path, peers_after_close: bool) -> None:  # type: ignore[no-untyped-def]
    eid = earnings_event(conn, doc_storage)
    q = post_market_quotes(peers_after_close)

    # the move is detected against the regular close (OQ-55)
    mv = detect_market_move(q, NVDA, ASOF, regular_close_mid=100.0)
    assert mv.triggered and mv.move_pct == pytest.approx(8.0, abs=1e-6) and mv.reference == "regular_close"
    assert mv.trigger is not None and (mv.trigger.trigger_type, mv.trigger.trigger_ref) == (
        "market_move",
        "move_abs_v1",
    )

    # analysis of the post-market reaction
    out = publish_explanation(conn, eid, NVDA, ASOF, ASOF + timedelta(seconds=5), q, weights=W)
    assert out.publish.status == "published"
    mr = out.reaction.market_reaction
    assert mr["stock_return_pct"] == pytest.approx(8.0, abs=1e-6)

    # the snapshot for the move (AC-39), built once the analysis is published (point in time: 10 s later)
    from sr.snapshot.builder import Trigger

    closes = {NVDA: 100.0, **{p: 50.0 for p in PEERS}}
    trig = Trigger("market_move", mv.trigger.trigger_ref, ASOF + timedelta(seconds=10))
    snap = build_snapshot(
        conn,
        NVDA,
        trig,
        q[q["ts"] >= q["ts"].max() - timedelta(seconds=60)],
        closes,
        ASOF + timedelta(seconds=11),
    ).row
    assert snap["trigger_type"] == "market_move" and snap["market_state"] == "post_market"
    assert snap["event_analysis_ids"] == [out.publish.analysis_id] and snap["new_catalyst_found"] is True
    assert snap["prediction_readiness"]["stock_reaction"]["status"] == "not_applicable"  # D-28
    assert snap["day_return_pct"] == pytest.approx(8.0, abs=1e-6)  # absolute move always shown
    if not peers_after_close:  # AC-40
        assert mr["relative_return_pp"] is None and mr["missing_reason"] == "benchmark_unavailable"

    # no regular_60m forecast is published from the post-market (AC-39, D-28)
    from tests.test_forecast import models

    m = models(conn, tmp_path)
    res = forecast_snapshot(
        conn,
        snap["snapshot_id"],
        FrameProvider(q),
        m,
        _empty_history(),
        ASOF + timedelta(seconds=12),
        feature_dir=tmp_path,
    )
    assert {p["status"] for p in res.predictions} == {"abstained"}
    assert {p["abstain_reason"] for p in res.predictions} == {"market_closed"}
    assert (
        conn.execute("select count(*) as n from predictions where status = 'published'").fetchone()["n"] == 0
    )

    # the next session's window starts no earlier than 09:31:00 ET the next day (D-10)
    assert next_session_start_bound(ASOF) == et_to_utc(date(2026, 12, 3), time(9, 31))


def test_ac40_post_market_summary_wording(conn) -> None:  # type: ignore[no-untyped-def]
    q = post_market_quotes(peers_after_close=False)
    mv = detect_market_move(q, NVDA, ASOF, regular_close_mid=100.0)
    assert mv.trigger is not None
    closes = {NVDA: 100.0, **{p: 50.0 for p in PEERS}}
    w = W
    from sr.snapshot import builder

    real = builder.benchmark_version
    try:
        builder.benchmark_version = lambda conn, sec, d: (
            "bmv_semis_peer_ex_nvda_v1",
            w,
        )  # 3-peer synthetic basket
        snap = build_snapshot(
            conn, NVDA, mv.trigger, q[q["ts"] >= q["ts"].max() - timedelta(seconds=60)], closes, ASOF
        ).row
    finally:
        builder.benchmark_version = real
    assert snap["day_relative_pp"] is None and snap["day_return_pct"] == pytest.approx(8.0, abs=1e-6)
    assert "盘后基准不可计算" in snap["explanation_summary"]  # AC-40 wording
    assert snap["market_state"] == "post_market"


def test_regular_hours_window_reference() -> None:
    t = et_to_utc(D, time(11, 0))
    q = visible(
        make_quotes(
            {NVDA: ramp(100, 103.5, t - timedelta(minutes=10), t - timedelta(minutes=1))},
            t - timedelta(minutes=20),
            t,
        ),
        t,
    )
    mv = detect_market_move(q, NVDA, t)
    assert mv.triggered and mv.reference == "window_start" and mv.move_pct == pytest.approx(3.5, abs=1e-6)
    calm = visible(
        make_quotes({NVDA: ramp(100, 101, t - timedelta(minutes=10), t)}, t - timedelta(minutes=20), t), t
    )
    assert detect_market_move(calm, NVDA, t).triggered is False


def _empty_history():  # type: ignore[no-untyped-def]
    import pandas as pd

    return pd.DataFrame(columns=["security_id", "session_date", "t0_ts", "end_ts", "relative_return_pp"])
