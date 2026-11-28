"""DP 2.01-2.06 acceptance on a simulated live session: AC-17 (four securities, 5-minute snapshots, event snapshots
within 60 s) and AC-18 (2-minute feed outage -> stale snapshot, slot forecast abstained/stale_quote, reasons in the
quality report). The feed is the SYNTHETIC fixture (虚构) replayed as live ticks; nothing here is market data."""

from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from sr.calendar import get_calendar
from sr.calendar.calendar import et_to_utc
from sr.config import load
from sr.eval.quality_report import quality_report, to_markdown
from sr.events.merge import EvidenceIn, Link, attach_evidence
from sr.jobs.live_day import run_live_day
from sr.marketdata.live import Outage, SimulatedFeed
from tests.test_live_evidence import Clock, FakeSource

DAY = date(2026, 12, 1)
PILOT = ["sec_amd", "sec_avgo", "sec_mu", "sec_nvda"]


def setup(raw: pd.DataFrame, outages=()):  # type: ignore[no-untyped-def]
    symbols = dict(raw[["symbol", "security_id"]].drop_duplicates().itertuples(index=False, name=None))
    first = raw[raw["ts"] == raw["ts"].min()]
    closes = {r.security_id: float((r.bid + r.ask) / 2) for r in first.itertuples()}
    return SimulatedFeed(raw, symbols, outages), symbols, closes


def subject_analyzer(conn, dv: str, now: datetime) -> list[str]:  # type: ignore[no-untyped-def]
    """Test analyzer: each synthetic press release is an order event for its subject company."""
    r = conn.execute(
        """select d.external_ref, d.subject_company_ids from source_document_versions v join source_documents d using (doc_id)
            where v.doc_version_id = %s""",
        (dv,),
    ).fetchone()
    sec = "sec_" + r["subject_company_ids"][0].removeprefix("co_")
    m = attach_evidence(
        conn,
        f"deal:{r['external_ref']}",
        "customer_demand",
        EvidenceIn(
            dv,
            f"{r['external_ref']}: order announced (synthetic)",
            {},
            "primary_confirmed",
            f"o:{r['external_ref']}",
        ),
        links=[Link(sec, "subject")],
        now=now,
    )
    return [m.event_id]


def test_ac17_four_securities_full_live_session(conn, raw_quotes, doc_storage) -> None:  # type: ignore[no-untyped-def]
    feed, symbols, closes = setup(raw_quotes)
    releases = [
        (et_to_utc(DAY, time(h, m, 7)), f"{co}-pr-{h}{m:02d}", "Synthetic press release")
        for (h, m), co in zip(
            [(9, 50), (10, 41), (11, 17), (12, 3), (13, 29), (14, 11), (14, 56), (15, 33)],
            ["amd", "nvda", "mu", "avgo", "amd", "nvda", "mu", "avgo"],
            strict=True,
        )
    ]
    src = FakeSource("src_company_ir", Clock(et_to_utc(DAY, time(9, 0))), releases)

    def start(clock, store) -> None:  # type: ignore[no-untyped-def]
        src.clock = clock  # the source sees the simulated clock

    res = run_live_day(
        conn,
        feed,
        symbols,
        DAY,
        PILOT,
        closes,
        poller_sources=[src],
        analyzers={"company_ir": subject_analyzer},
        scan_every_s=300,
        storage=doc_storage,
        on_start=start,  # move rules: test_market_move_rules
    )

    need = int(load("live")["targets"]["min_scheduled_snapshots"])
    for sec in PILOT:
        assert res.snapshots[sec].get("scheduled", 0) >= need, (sec, res.snapshots[sec])
    sched = conn.execute(
        """select security_id, min(analysis_as_of) as a, max(analysis_as_of) as b from security_state_snapshots
            where trigger_type = 'scheduled' group by 1"""
    ).fetchall()
    s = get_calendar().session(DAY)
    assert all(r["a"] == s.open_at and r["b"] == s.close_at - timedelta(minutes=5) for r in sched)
    # every release gives event snapshots for its subject, and the read-through links get their own
    assert all(res.snapshots[sec].get("event", 0) >= 2 for sec in PILOT)
    ev_secs = {
        (r["trigger_ref"], r["security_id"])
        for r in conn.execute(
            "select trigger_ref, security_id from security_state_snapshots where trigger_type = 'event'"
        )
    }
    amd_events = {e for e, sec in ev_secs if sec == "sec_amd"}
    assert any((e, "sec_nvda") in ev_secs for e in amd_events)  # NVDA competitor read-through
    assert len(res.event_latency_s) >= 8
    assert res.event_latency_p95_s is not None and res.event_latency_p95_s <= float(
        load("live")["targets"]["event_snapshot_p95_s"]
    )
    assert min(res.event_latency_s) >= 0
    q = res.jobs
    assert q.get("dead", 0) == 0 and q.get("retry_wait", 0) == 0 and q.get("queued", 0) == 0
    assert res.ingest_metrics["latency_p95_ms"] <= 250


def history_before(day: date, n_days: int = 6) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    cal = get_calendar()
    s = cal.previous_open_session(day)
    rows = []
    for _ in range(n_days):
        assert s.open_at is not None
        for i in range(66):
            t0 = s.open_at + timedelta(minutes=5 * i, seconds=5)
            rows.append(
                {
                    "security_id": "sec_nvda",
                    "session_date": s.session_date,
                    "t0_ts": pd.Timestamp(t0),
                    "end_ts": pd.Timestamp(t0 + timedelta(minutes=60)),
                    "relative_return_pp": float(rng.normal(0, 0.6)),
                }
            )
        s = cal.previous_open_session(s.session_date)
    return pd.DataFrame(rows)


def test_ac18_feed_outage_gives_stale_and_abstained(conn, raw_quotes, tmp_path, doc_storage) -> None:  # type: ignore[no-untyped-def]
    from sr.pipeline.orchestrator import RunContext
    from tests.test_forecast import models

    o0, o1 = et_to_utc(DAY, time(9, 58, 45)), et_to_utc(DAY, time(10, 0, 45))  # 2 minutes, whole feed
    feed, symbols, closes = setup(raw_quotes, [Outage(o0, o1)])
    m, h = models(conn, tmp_path), history_before(DAY)

    _store: dict = {}  # type: ignore[type-arg]

    def run_context(at: datetime, lag: timedelta) -> RunContext:
        return RunContext(_store["s"], m, h, prev_close=closes, feature_dir=tmp_path, publish_lag=lag)

    quiet = FakeSource("src_company_ir", Clock(o0), [])  # polled, nothing new: collection runs exist

    def start(clock, store) -> None:  # type: ignore[no-untyped-def]
        _store["s"] = store
        quiet.clock = clock

    run_live_day(
        conn,
        feed,
        symbols,
        DAY,
        ["sec_nvda"],
        closes,
        run_context=run_context,
        slots=True,
        scan_every_s=300,
        until=et_to_utc(DAY, time(10, 12)),
        on_start=start,
        poller_sources=[quiet],
        storage=doc_storage,
    )

    snap = conn.execute(
        """select * from security_state_snapshots where security_id = 'sec_nvda' and trigger_type = 'scheduled'
            and analysis_as_of = %s""",
        (et_to_utc(DAY, time(10, 0)),),
    ).fetchone()
    assert snap["data_quality"] == "stale" and snap["run_state"] == "degraded"
    assert any(i["issue"] == "stale_quotes" for i in snap["quality_issues"])
    later = conn.execute(
        """select data_quality from security_state_snapshots where security_id = 'sec_nvda' and trigger_type = 'scheduled'
            and analysis_as_of = %s""",
        (et_to_utc(DAY, time(10, 5)),),
    ).fetchone()
    assert later["data_quality"] == "ok"  # recovers once ticks resume
    slot = conn.execute(
        "select target_row_id, status, abstain_reason from predictions where schedule_slot_id = 's1000' order by 1"
    ).fetchall()
    assert [(p["target_row_id"], p["status"], p["abstain_reason"]) for p in slot] == [
        ("tgt_regular_60m_move_v1", "abstained", "stale_quote"),
        ("tgt_regular_60m_v1", "abstained", "stale_quote"),
    ]
    rep = quality_report(conn, DAY, DAY, et_to_utc(DAY, time(10, 12)))
    nv = rep["securities"]["sec_nvda"]
    assert nv["predictions"]["abstain_reasons"]["stale_quote"] == 2
    assert nv["predictions"]["primary"]["abstain_reasons"]["stale_quote"] == 2
    assert nv["snapshots"]["data_quality"]["stale"] >= 1 and nv["snapshots"]["issues"]["stale_quotes"] >= 1
    assert "stale_quote 2" in to_markdown(rep)
