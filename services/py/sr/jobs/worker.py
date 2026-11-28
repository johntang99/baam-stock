"""Job worker (DP 2.02; `uv run sr worker`).

A handler is `fn(conn, job, now) -> None`. It runs inside one transaction together with marking the job
`succeeded`, so a crash between the two is impossible: either the work and the completion commit, or neither does
and the job is retried. An exception rolls the handler's writes back and records the failed try (backoff, then the
dead letter after `max_attempts`). Handlers must be idempotent: a reclaimed job can run a second time.

Pipeline jobs (`pipeline_step`, `run_forecast`) are the exception: the orchestrator commits each step row as it
goes, so a failed step stays recorded and the retry resumes from it (AC-35). They run outside the worker
transaction and are marked succeeded afterwards.
"""

from __future__ import annotations

import os
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sr.config import load
from sr.db import Conn
from sr.jobs.queue import Job, claim, complete, fail

Handler = Callable[[Conn, Job, datetime], Any]
Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(UTC)


@dataclass
class RunRecord:
    job_id: str
    job_type: str
    status: str  # succeeded | retry_wait | dead | no_handler
    started_at: datetime
    finished_at: datetime
    error: str | None = None


@dataclass
class Worker:
    conn: Conn
    handlers: dict[str, Handler]
    clock: Clock = system_clock
    worker_id: str = field(default_factory=lambda: f"{socket.gethostname()}:{os.getpid()}")
    log: list[RunRecord] = field(default_factory=list)
    own_transaction: frozenset[str] = frozenset({"pipeline_step", "run_forecast"})

    def run_once(self, limit: int | None = None) -> list[RunRecord]:
        """Claim and run the jobs that are due now. Returns what happened to each."""
        n = int(limit or load("jobs")["worker"]["batch"])
        jobs = claim(self.conn, self.worker_id, self.clock(), list(self.handlers) or None, n)
        out = [self._run(j) for j in jobs]
        self.log += out
        return out

    def drain(self, max_jobs: int = 10_000) -> list[RunRecord]:
        """Run due jobs until none is left (a retry scheduled in the future is not due)."""
        out: list[RunRecord] = []
        while len(out) < max_jobs:
            got = self.run_once()
            if not got:
                break
            out += got
        return out

    def _run(self, job: Job) -> RunRecord:
        started = self.clock()
        fn = self.handlers.get(job.job_type)
        if fn is None:  # claim() filters by handler type, so this only happens if handlers change mid-run
            st = fail(self.conn, job, self.worker_id, f"no handler for {job.job_type}", started)
            return RunRecord(job.job_id, job.job_type, st, started, self.clock(), "no_handler")
        try:
            if job.job_type in self.own_transaction:
                fn(self.conn, job, started)
                complete(self.conn, job.job_id, self.worker_id)
            else:
                with self.conn.transaction():
                    fn(self.conn, job, started)
                    complete(self.conn, job.job_id, self.worker_id)
            return RunRecord(job.job_id, job.job_type, "succeeded", started, self.clock())
        except Exception as e:  # recorded on the job; the worker keeps going
            err = f"{type(e).__name__}: {e}"
            st = fail(self.conn, job, self.worker_id, err, self.clock())
            return RunRecord(job.job_id, job.job_type, st, started, self.clock(), err)

    def run_forever(self, stop: Callable[[], bool] = lambda: False) -> None:
        idle = float(load("jobs")["worker"]["poll_interval_s"])
        while not stop():
            if not self.run_once():
                time.sleep(idle)
