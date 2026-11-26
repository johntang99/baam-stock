"""Event analysis versions under an optimistic lock (DC §1 乐观锁, §4 并发, §7; AC-08).

A worker reads the event's row_version and the latest analysis for (event, security), computes, then publishes:
  UPDATE events SET row_version = row_version + 1 ... WHERE row_version = :expected
If that fails (someone else published), it re-reads: if the competing version's input watermark
(analysis_as_of) is at least as new as its own, it discards its result; otherwise it retries on top of it.
A worker whose watermark is older than the latest published version always discards — an old task can never
overwrite a newer analysis. Versions are append-only; each supersedes the previous one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sr.db import ConflictStaleVersion, Conn, jsonb
from sr.ids import new_id
from sr.timeguard import ensure_utc

JSONB_FIELDS = (
    "facts",
    "expectation_comparison",
    "impact",
    "priority",
    "market_reaction",
    "market_explanation",
    "reasoning_trace",
    "historical_cases",
    "scenarios",
    "model_versions",
    "prediction_readiness",
)
TEXT_FIELDS = ("analysis_kind", "missing_reason", "rule_version")
ARRAY_FIELDS = ("evidence_ids", "data_gaps")


@dataclass(frozen=True)
class Snapshot:
    event_id: str
    security_id: str
    row_version: int
    latest_version: int | None
    latest_analysis_id: str | None
    latest_as_of: datetime | None


@dataclass(frozen=True)
class PublishResult:
    status: Literal["published", "discarded"]
    analysis_id: str | None
    analysis_version: int | None
    reason: str = ""


def read_state(conn: Conn, event_id: str, security_id: str) -> Snapshot:
    ev = conn.execute("select row_version from events where event_id = %s", (event_id,)).fetchone()
    if ev is None:
        raise KeyError(event_id)
    last = conn.execute(
        """select analysis_id, analysis_version, analysis_as_of from event_analysis_versions
           where event_id = %s and security_id = %s order by analysis_version desc limit 1""",
        (event_id, security_id),
    ).fetchone()
    return Snapshot(
        event_id,
        security_id,
        ev["row_version"],
        last["analysis_version"] if last else None,
        last["analysis_id"] if last else None,
        last["analysis_as_of"] if last else None,
    )


def try_publish(
    conn: Conn, snap: Snapshot, analysis_as_of: datetime, payload: dict[str, Any], published_at: datetime
) -> PublishResult:
    """One attempt against the state read in `snap`. Raises ConflictStaleVersion if the event moved on."""
    as_of = ensure_utc(analysis_as_of, "analysis_as_of").to_pydatetime()
    if snap.latest_as_of is not None and as_of <= snap.latest_as_of:
        return PublishResult(
            "discarded",
            None,
            None,
            f"input watermark {as_of.isoformat()} not newer than published {snap.latest_as_of.isoformat()}",
        )
    version = (snap.latest_version or 0) + 1
    with conn.transaction():
        upd = conn.execute(
            """update events set row_version = row_version + 1,
                 current_analysis_version = greatest(coalesce(current_analysis_version, 0), %s)
               where event_id = %s and row_version = %s returning row_version""",
            (version, snap.event_id, snap.row_version),
        ).fetchone()
        if upd is None:
            raise ConflictStaleVersion(f"event {snap.event_id}: row_version {snap.row_version} is stale")
        aid = new_id("eav")
        cols = [
            "analysis_id",
            "event_id",
            "security_id",
            "analysis_version",
            "analysis_as_of",
            "published_at",
            "supersedes_analysis_id",
        ]
        vals: list[Any] = [
            aid,
            snap.event_id,
            snap.security_id,
            version,
            as_of,
            ensure_utc(published_at, "published_at").to_pydatetime(),
            snap.latest_analysis_id,
        ]
        for k in JSONB_FIELDS:
            if k in payload:
                cols.append(k)
                vals.append(jsonb(payload[k]))
        for k in (*TEXT_FIELDS, *ARRAY_FIELDS):
            if k in payload:
                cols.append(k)
                vals.append(payload[k])
        conn.execute(
            f"insert into event_analysis_versions ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
            vals,
        )
    return PublishResult("published", aid, version)


def publish_analysis(
    conn: Conn,
    event_id: str,
    security_id: str,
    analysis_as_of: datetime,
    compute: Callable[[Snapshot], dict[str, Any]],
    published_at: datetime,
    max_attempts: int = 3,
) -> PublishResult:
    """Read -> compute -> conditional write, retrying on conflicts while this input is still the newest."""
    for _ in range(max_attempts):
        snap = read_state(conn, event_id, security_id)
        if snap.latest_as_of is not None and ensure_utc(analysis_as_of, "as_of") <= snap.latest_as_of:
            return PublishResult(
                "discarded", None, None, "a newer or equal input watermark is already published"
            )
        try:
            return try_publish(conn, snap, analysis_as_of, compute(snap), published_at)
        except ConflictStaleVersion:
            continue
    raise ConflictStaleVersion(f"event {event_id}: gave up after {max_attempts} conflicting attempts")
