"""Snapshot data quality and run state (DP 1.23; DC security_state_snapshots; AC-49; OQ-44, OQ-53).

data_quality (regular hours): failed = no qualifying stock quote yet this session; stale = the latest qualifying
quote is older than `stale_after_s`; partial = relative return unavailable, a source failed / was late in the
collection run, or there was no collection run; ok otherwise. run_state: ok -> complete, stale / partial ->
degraded (results, but something missing), failed -> failed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sr.config import load
from sr.timeguard import ensure_utc

RUN_STATE = {"ok": "complete", "stale": "degraded", "partial": "degraded", "failed": "failed"}
PARTIAL_ISSUES = ("source_fetch_failed", "no_collection_run", "timeout", "error", "latency")


def source_issues(collection_run: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Per-source problems recorded in a collection run's sources_polled (OQ-53)."""
    if not collection_run:
        return []
    limit = int(load("snapshot")["quality"]["source_latency_max_ms"])
    out: list[dict[str, Any]] = []
    for s in collection_run.get("sources_polled") or []:
        if s.get("status") not in (None, "ok"):
            out.append({"source_id": s.get("source_id"), "issue": s["status"]})
        elif int(s.get("latency_ms") or 0) > limit:
            out.append(
                {
                    "source_id": s.get("source_id"),
                    "issue": "latency",
                    "lag_s": round(int(s["latency_ms"]) / 1000),
                }
            )
    return out


def assess(
    *,
    regular: bool,
    session_open_at: datetime | None,
    market_watermark: datetime,
    as_of: datetime,
    day_return_pct: float | None,
    relative_pp: float | None,
    issues: list[dict[str, Any]],
) -> tuple[str, str, list[dict[str, Any]]]:
    """(data_quality, run_state, issues). `issues` comes in with the evidence / source issues and is extended."""
    stale = timedelta(seconds=int(load("snapshot")["quality"]["stale_after_s"]))
    lag = ensure_utc(as_of, "as_of") - ensure_utc(market_watermark, "market_watermark")
    out = list(issues)
    if regular and (session_open_at is None or market_watermark < session_open_at):
        quality = "failed"
        out.append({"issue": "no_qualifying_quote"})
    elif regular and lag > stale:
        quality = "stale"
        out.append({"issue": "stale_quotes", "lag_s": int(lag.total_seconds())})
    elif regular and relative_pp is None:
        quality = "partial"
        out.append({"issue": "previous_close_missing" if day_return_pct is None else "benchmark_unavailable"})
    elif any(i.get("issue") in PARTIAL_ISSUES for i in out):
        quality = "partial"
    else:
        quality = "ok"
    return quality, RUN_STATE[quality], out
