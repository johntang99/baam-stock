"""Simulated live session (DP 2.01-2.06 acceptance; AC-17, AC-18; OQ-58). SYNTHETIC feed only.

`run_live_day()` drives one session the way the live system runs, on a simulated clock:
feed ticks -> md-ingest 1-second layer -> evidence poller -> market-move scanner -> job worker
(scheduled snapshots, event snapshots, slot forecasts, settlement). The clock moves in `step_s` steps and also
advances by the real time the work takes, so a slow handler makes later work late, as it would live; latencies
are measured on that clock (e.g. event `available_at` -> snapshot `published_at`).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

from sr.calendar import get_calendar
from sr.config import load
from sr.db import Conn
from sr.evidence.live import LivePoller
from sr.jobs.handlers import LiveContext, live_snapshot_quotes, make_handlers
from sr.jobs.queue import counts
from sr.jobs.scheduler import enqueue_move_snapshot, enqueue_session
from sr.jobs.worker import Worker
from sr.marketdata.live import LiveIngest, LiveQuoteStore, SimulatedFeed, advance
from sr.snapshot.builder import benchmark_version
from sr.snapshot.triggers import MoveScanner
from sr.timeguard import ensure_utc


class SimClock:
    """now() = the last set time + the real time elapsed since it was set (scale 1)."""

    def __init__(self, t: datetime) -> None:
        self.set(t)

    def set(self, t: datetime) -> None:
        self._t, self._mark = ensure_utc(t, "t").to_pydatetime(), time.monotonic()

    def __call__(self) -> datetime:
        return self._t + timedelta(seconds=time.monotonic() - self._mark)


@dataclass
class LiveDayResult:
    session_date: date
    snapshots: dict[str, dict[str, int]]
    event_latency_s: list[float]
    jobs: dict[str, int]
    ingest_metrics: dict[str, Any]
    move_hits: list[dict[str, Any]] = field(default_factory=list)
    poll_records: int = 0

    @property
    def event_latency_p95_s(self) -> float | None:
        return float(np.percentile(self.event_latency_s, 95)) if self.event_latency_s else None


def run_live_day(
    conn: Conn,
    feed: SimulatedFeed,
    symbols: dict[str, str],
    session_date: date,
    security_ids: list[str],
    prev_close: dict[str, float | None],
    poller_sources: list[Any] | None = None,
    analyzers: dict[str, Any] | None = None,
    run_context: Any = None,
    slots: bool = False,
    step_s: float | None = None,
    scan_every_s: float | None = None,
    until: datetime | None = None,
    storage: Any = None,
    on_start: Any = None,
) -> LiveDayResult:
    """`on_start(clock, store)` is called once before the loop (sources and run contexts that need them)."""
    s = get_calendar().session(session_date)
    if not s.is_open or s.open_at is None or s.close_at is None:
        raise ValueError(f"{session_date} is not a trading day")
    step = timedelta(seconds=float(step_s or load("live")["sim_step_s"]))
    start = s.open_at - timedelta(
        minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]) + 1
    )
    end = ensure_utc(until, "until").to_pydatetime() if until else s.close_at + timedelta(minutes=1)
    clock = SimClock(start)
    store = LiveQuoteStore(clock, feed.source_id, synthetic=True)
    ingest = LiveIngest(store, symbols)
    if on_start is not None:
        on_start(clock, store)
    ctx = LiveContext(store, prev_close, clock, run_context=run_context)
    if analyzers is not None:
        ctx.analyzers = analyzers
    handlers = make_handlers(ctx)
    if run_context is None:
        handlers.pop("run_forecast")
    worker = Worker(conn, handlers, clock=clock, worker_id="sim-live")
    poller = (
        LivePoller(conn, poller_sources, clock, storage=storage, collect_for=security_ids)
        if poller_sources
        else None
    )
    scanner = MoveScanner()
    scan_every = timedelta(seconds=float(scan_every_s or load("market_move_rules")["scan_every_s"]))
    enqueue_session(conn, session_date, security_ids, slots=slots)
    weights = {sec: benchmark_version(conn, sec, session_date)[1] for sec in security_ids}
    all_ids = sorted({*security_ids, *(c for w in weights.values() for c in w)})

    t, next_scan, polls, hits = start, s.open_at, 0, []
    while t <= end:
        clock.set(t)
        advance(feed, ingest, t)
        if poller is not None:
            polls += len(poller.poll_due())
        if s.open_at <= t < s.close_at and t >= next_scan:
            q = live_snapshot_quotes(store, all_ids, t)  # one evaluation per scan for every security
            for sec in security_ids:
                for c in scanner.scan(q, sec, t, weights=weights[sec]):
                    enqueue_move_snapshot(conn, sec, str(c.rule_id), t)
                    hits.append({"security_id": sec, "rule_id": c.rule_id, "at": t, "move": c.move_pct})
            next_scan = t + scan_every
        worker.drain()
        t = max(t + step, ensure_utc(clock(), "clock").floor("1s").to_pydatetime())

    snaps: dict[str, dict[str, int]] = {}
    for r in conn.execute(
        """select security_id, trigger_type, count(*) as n from security_state_snapshots
            where session_date = %s group by 1, 2""",
        (session_date,),
    ).fetchall():
        snaps.setdefault(r["security_id"], {})[r["trigger_type"]] = int(r["n"])
    lat = [
        float(r["d"])
        for r in conn.execute(
            """select extract(epoch from (sn.published_at - v.available_at)) as d
                 from security_state_snapshots sn
                 join event_evidence e on e.event_id = sn.trigger_ref
                 join source_document_versions v on v.doc_version_id = e.doc_version_id
                where sn.trigger_type = 'event' and sn.session_date = %s""",
            (session_date,),
        ).fetchall()
    ]
    return LiveDayResult(session_date, snaps, lat, counts(conn), ingest.metrics(clock()), hits, polls)
