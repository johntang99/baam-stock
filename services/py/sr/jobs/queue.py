"""Postgres job queue (DP 2.02; DC jobs; OQ-58).

- enqueue(): idempotent on `idempotency_key` — a second enqueue returns the existing job id and changes nothing.
- claim(): one statement, `FOR UPDATE SKIP LOCKED`, so concurrent workers never take the same job. Jobs whose lock
  is older than `lock_timeout_s` (a crashed worker) are first put back to `retry_wait`.
- complete() / fail(): a failed try waits `2^attempts x base_s` (capped), and after `max_attempts` tries the job is
  `dead` (dead letter) and a `pipeline_failed` alert is opened. Nothing is deleted.

Every function takes `now` explicitly so the queue runs on a simulated clock in replay and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sr.config import load
from sr.db import Conn, jsonb
from sr.ids import new_id
from sr.timeguard import ensure_utc


@dataclass(frozen=True)
class Job:
    job_id: str
    job_type: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    pipeline_run_id: str | None
    run_after: datetime


def _utc(t: datetime) -> datetime:
    return ensure_utc(t, "now").to_pydatetime()


def enqueue(
    conn: Conn,
    job_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    run_after: datetime,
    pipeline_run_id: str | None = None,
    max_attempts: int | None = None,
) -> tuple[str, bool]:
    """(job_id, created). An existing key returns the existing job unchanged."""
    cfg = load("jobs")
    jid = new_id("job")
    row = conn.execute(
        """insert into jobs (job_id, job_type, pipeline_run_id, payload, idempotency_key, max_attempts, run_after)
           values (%s, %s::job_type, %s, %s, %s, %s, %s) on conflict (idempotency_key) do nothing returning job_id""",
        (
            jid,
            job_type,
            pipeline_run_id,
            jsonb(payload),
            idempotency_key,
            int(max_attempts or cfg["default_max_attempts"]),
            _utc(run_after),
        ),
    ).fetchone()
    if row is not None:
        return row["job_id"], True
    old = conn.execute("select job_id from jobs where idempotency_key = %s", (idempotency_key,)).fetchone()
    assert old is not None
    return old["job_id"], False


def reclaim_stale(conn: Conn, now: datetime) -> int:
    """Running jobs whose lock is older than the timeout go back to retry_wait (their try counts as used)."""
    t = _utc(now)
    cut = t - timedelta(seconds=int(load("jobs")["lock_timeout_s"]))
    rows = conn.execute(
        """update jobs set status = 'retry_wait', locked_by = null, locked_at = null, run_after = %s,
                  last_error = coalesce(last_error || ' | ', '') || 'lock_timeout'
            where status = 'running' and locked_at < %s returning job_id""",
        (t, cut),
    ).fetchall()
    return len(rows)


def claim(
    conn: Conn, worker_id: str, now: datetime, job_types: list[str] | None = None, limit: int = 1
) -> list[Job]:
    t = _utc(now)
    reclaim_stale(conn, t)
    rows = conn.execute(
        """update jobs j set status = 'running', locked_by = %s, locked_at = %s, attempts = j.attempts + 1
            where j.job_id in (
                select job_id from jobs
                 where status in ('queued', 'retry_wait') and run_after <= %s
                   and (%s::job_type[] is null or job_type = any(%s::job_type[]))
                 order by run_after, job_id
                 limit %s
                 for update skip locked)
           returning j.*""",
        (worker_id, t, t, job_types, job_types, limit),
    ).fetchall()
    return [
        Job(
            r["job_id"],
            r["job_type"],
            dict(r["payload"] or {}),
            int(r["attempts"]),
            int(r["max_attempts"]),
            r["pipeline_run_id"],
            r["run_after"],
        )
        for r in sorted(rows, key=lambda r: (r["run_after"], r["job_id"]))
    ]


def complete(conn: Conn, job_id: str, worker_id: str) -> None:
    conn.execute(
        """update jobs set status = 'succeeded', locked_by = null, locked_at = null
            where job_id = %s and status = 'running' and locked_by = %s""",
        (job_id, worker_id),
    )


def backoff(attempts: int) -> timedelta:
    cfg = load("jobs")["backoff"]
    return timedelta(seconds=min(float(cfg["max_s"]), (2 ** int(attempts)) * float(cfg["base_s"])))


def fail(conn: Conn, job: Job, worker_id: str, error: str, now: datetime) -> str:
    """Record a failed try. Returns the new status: retry_wait or dead (dead letter + alert)."""
    t = _utc(now)
    msg = error[:1000]
    if job.attempts >= job.max_attempts:
        conn.execute(
            """update jobs set status = 'dead', locked_by = null, locked_at = null, last_error = %s
                where job_id = %s and locked_by = %s""",
            (msg, job.job_id, worker_id),
        )
        dl = load("jobs")["dead_letter"]
        conn.execute(
            """insert into alerts (alert_id, severity, kind, ref, opened_at, message)
               values (%s, %s::alert_severity, %s::alert_kind, %s, %s, %s)""",
            (
                new_id("alert"),
                dl["alert_severity"],
                dl["alert_kind"],
                job.job_id,
                t,
                f"job {job.job_type} dead after {job.attempts} attempts: {msg[:300]}",
            ),
        )
        return "dead"
    conn.execute(
        """update jobs set status = 'retry_wait', locked_by = null, locked_at = null, last_error = %s, run_after = %s
            where job_id = %s and locked_by = %s""",
        (msg, t + backoff(job.attempts), job.job_id, worker_id),
    )
    return "retry_wait"


def counts(conn: Conn) -> dict[str, int]:
    return {
        r["status"]: int(r["n"])
        for r in conn.execute("select status, count(*) as n from jobs group by status").fetchall()
    }
