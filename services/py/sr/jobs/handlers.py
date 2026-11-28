"""Job handlers for the live worker (DP 2.02-2.04; DC §6.1; OQ-58).

`make_handlers(ctx)` binds the handlers to one `LiveContext` (the quote store, previous closes, clock and optional
pipeline context). Every handler is idempotent: snapshots merge on watermarks, pipeline runs on their key,
settlement on its version rule, and event links / analyses on their own keys.

- build_snapshot: the snapshot at `payload.as_of` from quotes received by then; published_at = the clock.
- run_forecast:   the full pipeline for one sched-0.1 slot (`trigger_type = scheduled`); a late run is
                  `slot_missed` through the forecast rules, never reissued.
- settle_due:     settles one prediction with the quotes that have arrived.
- analyze_event:  dispatches a new document version to its template analyzer by source kind, adds read-through
                  links (DP 2.05), explains the event for each linked pilot security and queues event snapshots.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sr.calendar import get_calendar
from sr.config import load
from sr.db import Conn
from sr.events.exposure import read_through_links
from sr.jobs.queue import Job
from sr.jobs.scheduler import enqueue_event_snapshot
from sr.marketdata.quote_rules import evaluate_quotes
from sr.pipeline.orchestrator import RunContext, _snapshot_quotes, run_pipeline
from sr.snapshot.builder import Trigger, benchmark_version, build_snapshot
from sr.timeguard import ensure_utc

Analyzer = Callable[[Conn, str, datetime], list[str]]  # (conn, doc_version_id, now) -> event ids


def _t(s: str) -> datetime:
    return ensure_utc(pd.Timestamp(s), "t").to_pydatetime()


def live_snapshot_quotes(store: Any, ids: list[str], as_of: datetime) -> pd.DataFrame:
    """Evaluated quotes for a snapshot. In regular hours only the warm-up + stale window is read (the market
    watermark falls back to the previous snapshot when nothing qualifies); outside them the Phase 1 read."""
    session = get_calendar().session_for_instant(as_of)
    if not (session.open_at and session.close_at and session.open_at <= as_of < session.close_at):
        return _snapshot_quotes(store, ids, as_of)
    warm = timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
    stale = timedelta(seconds=int(load("snapshot")["quality"]["stale_after_s"]))
    have = store.security_ids
    q = evaluate_quotes(store.quotes_1s([i for i in ids if i in have], as_of - warm - stale, as_of))
    return q[q["received_at"] <= pd.Timestamp(as_of)].reset_index(drop=True)


def policy_analyzer(conn: Conn, doc_version_id: str, now: datetime) -> list[str]:
    from sr.events.policy import process_policy_document

    out = process_policy_document(conn, doc_version_id, now, now)
    return [out.event_id] if out.event_id else []


DEFAULT_ANALYZERS: dict[str, Analyzer] = {
    "policy": policy_analyzer
}  # earnings needs the approved LLM run (1.18)


@dataclass
class LiveContext:
    store: Any  # LiveQuoteStore / ParquetQuoteStore: refuses reads past its clock
    prev_close: dict[str, float | None]
    clock: Callable[[], datetime]
    run_context: Callable[[datetime, timedelta], RunContext] | None = None  # (now, publish_lag) -> context
    analyzers: dict[str, Analyzer] = field(default_factory=lambda: dict(DEFAULT_ANALYZERS))
    log: list[dict[str, Any]] = field(default_factory=list)


def make_handlers(ctx: LiveContext) -> dict[str, Callable[[Conn, Job, datetime], Any]]:
    def snapshot(conn: Conn, job: Job, now: datetime) -> None:
        p = job.payload
        sec, as_of = p["security_id"], _t(p["as_of"])
        day = get_calendar().session_for_instant(as_of).session_date
        _, w = benchmark_version(conn, sec, day)
        q = live_snapshot_quotes(ctx.store, [sec, *w], as_of)
        r = build_snapshot(
            conn, sec, Trigger(p["trigger_type"], p.get("trigger_ref"), as_of), q, ctx.prev_close, ctx.clock()
        )
        ctx.log.append(
            {
                "job": "build_snapshot",
                "security_id": sec,
                "trigger_type": p["trigger_type"],
                "as_of": as_of,
                "snapshot_id": r.snapshot_id,
                "status": r.status,
                "published_at": r.row["published_at"],
            }
        )

    def forecast(conn: Conn, job: Job, now: datetime) -> None:
        if ctx.run_context is None:
            raise RuntimeError("run_forecast needs a run context (models, history)")
        p = job.payload
        at = _t(p["scheduled_for"])
        lag = max(ensure_utc(ctx.clock(), "clock").to_pydatetime() - at, timedelta(0)) + timedelta(
            milliseconds=600
        )
        res = run_pipeline(
            conn,
            [p["security_id"]],
            list(p["targets"]),
            "live",
            at,
            ctx.run_context(at, lag),
            trigger_type="scheduled",
        )
        ctx.log.append(
            {
                "job": "run_forecast",
                "security_id": p["security_id"],
                "slot_id": p["slot_id"],
                "pipeline_run_id": res.pipeline_run_id,
                "status": res.status,
            }
        )

    def settle_due(conn: Conn, job: Job, now: datetime) -> None:
        from sr.settle.settle import settle, weights_for

        pid = job.payload["prediction_id"]
        pr = conn.execute("select * from predictions where prediction_id = %s", (pid,)).fetchone()
        if pr is None:
            raise KeyError(pid)
        t = ensure_utc(ctx.clock(), "clock").to_pydatetime()
        w = weights_for(conn, pr["locked"]["benchmark_version_id"])
        warm = timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
        end = min(pr["published_at"] + timedelta(minutes=62), t)
        q = evaluate_quotes(ctx.store.quotes_1s([pr["security_id"], *w], pr["published_at"] - warm, end))
        settle(conn, pid, q[q["received_at"] <= pd.Timestamp(t)].reset_index(drop=True), t)

    def analyze(conn: Conn, job: Job, now: datetime) -> None:
        dv = job.payload["doc_version_id"]
        row = conn.execute(
            """select ds.kind from source_document_versions v join source_documents d using (doc_id)
                join data_sources ds on ds.source_id = d.source_id where v.doc_version_id = %s""",
            (dv,),
        ).fetchone()
        kind = row["kind"] if row else None
        fn = ctx.analyzers.get(str(kind))
        t = ensure_utc(ctx.clock(), "clock").to_pydatetime()
        if fn is None:
            ctx.log.append(
                {"job": "analyze_event", "doc_version_id": dv, "skipped": f"no_analyzer_for_{kind}"}
            )
            return
        from sr.events.explain import anchor_at, evidence_for, publish_explanation, quotes_for

        for ev in fn(conn, dv, t):
            read_through_links(conn, ev, t)
            links = conn.execute(
                """select l.security_id from event_security_links l join securities s using (security_id)
                    where l.event_id = %s and s.coverage_tier = 'pilot' order by 1""",
                (ev,),
            ).fetchall()
            for lk in links:
                sec = lk[
                    "security_id"
                ]  # explanation versions dedupe on their own inputs (sr.events.versions)
                day = get_calendar().session_for_instant(t).session_date
                _, w = benchmark_version(conn, sec, day)
                q = quotes_for(ctx.store, sec, list(w), t, anchor_at(evidence_for(conn, ev, t)))
                publish_explanation(
                    conn, ev, sec, t, ensure_utc(ctx.clock(), "clock").to_pydatetime(), q, weights=w
                )
                enqueue_event_snapshot(conn, sec, ev, ensure_utc(ctx.clock(), "clock").to_pydatetime())
            ctx.log.append(
                {
                    "job": "analyze_event",
                    "doc_version_id": dv,
                    "event_id": ev,
                    "securities": [r["security_id"] for r in links],
                }
            )

    return {
        "build_snapshot": snapshot,
        "run_forecast": forecast,
        "settle_due": settle_due,
        "analyze_event": analyze,
    }
