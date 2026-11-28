"""Live evidence polling (DP 2.04; D-15; OQ-60).

`LivePoller.poll_due()` polls each source whose cadence has come round, ingests what it returns (arrival_mode
`live`, available_at = when ingest finished) and lets ingest enqueue the `analyze_event` job for each new document
version. Re-delivered items dedupe on content hash (AC-07), so the overlap between polls is harmless.

A failed poll is recorded as a failure with backoff — never as "no new items" — so health checks (DP 2.11) can
tell `source_down` from a quiet source.

With `collect_for` (the live securities), each poll round also writes one collection run per security through
`run_collection` (DP 1.27, AC-56): the documents fetched once in the round are handed over pre-fetched, so the
collection log, the item dispositions and the snapshot evidence watermark (OQ-44) work the same live as in replay.
A source that failed in the round shows up in that run as `error`, which makes the snapshot `partial`. `LicensedNewsSource` is the interface for the licensed feed (D-15); it is
disabled and refuses to poll until the licence exists.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sr.config import load
from sr.db import Conn
from sr.evidence.ingest import IngestResult, ingest
from sr.evidence.sources.base import EvidenceSource, RawDocument
from sr.evidence.storage import LocalDocStorage
from sr.timeguard import ensure_utc


class SourceDisabled(RuntimeError):
    """The source is configured off (e.g. no licence); polling it is refused."""


class LicensedNewsSource:
    """Placeholder for the licensed news feed (D-15). Disabled: no vendor, no key, no request."""

    def __init__(self) -> None:
        cfg = load("live_evidence")["licensed_news"]
        self.source_id = str(cfg["source_id"])
        self.enabled = bool(cfg["enabled"])

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        raise SourceDisabled(f"{self.source_id}: licensed news is disabled until D-15 is signed")


@dataclass
class SourceState:
    source_id: str
    next_poll_at: datetime | None = None
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
    polls: int = 0
    failures: int = 0
    docs_new: int = 0  # new document versions (direct-ingest mode)
    docs_fetched: int = 0  # items handed to collection runs (collect mode; re-deliveries included)
    disabled: bool = False
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=500))


class _Prefetched:
    """One round's result of a source, replayed into run_collection without polling again."""

    def __init__(self, source_id: str, docs: list[RawDocument], error: Exception | None) -> None:
        self.source_id, self.docs, self.error = source_id, docs, error

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        if self.error is not None:
            raise self.error
        return list(self.docs)


@dataclass(frozen=True)
class PollRecord:
    source_id: str
    at: datetime
    status: str  # ok | failed | disabled
    results: list[IngestResult]
    error: str | None = None
    latency_ms: float | None = None
    collection_run_ids: tuple[str, ...] = ()


def _cadence(source_id: str) -> timedelta:
    c = load("live_evidence")["cadence_s"]
    return timedelta(seconds=float(c.get(source_id, c["default"])))


def _backoff(n: int) -> timedelta:
    b = load("live_evidence")["failure_backoff_s"]
    return timedelta(seconds=min(float(b["max"]), float(b["base"]) * 2 ** max(0, n - 1)))


class LivePoller:
    def __init__(
        self,
        conn: Conn,
        sources: list[EvidenceSource],
        clock: Callable[[], datetime],
        storage: LocalDocStorage | None = None,
        timer: Callable[[], float] | None = None,
        collect_for: list[str] | None = None,
    ) -> None:
        import time

        self.conn, self.sources, self.clock, self.storage = conn, list(sources), clock, storage
        self.collect_for = list(collect_for or [])
        self._window_to: dict[str, datetime] = {}
        self.timer = timer or time.monotonic
        self.state: dict[str, SourceState] = {
            s.source_id: SourceState(s.source_id, disabled=getattr(s, "enabled", True) is False)
            for s in self.sources
        }

    def poll_due(self) -> list[PollRecord]:
        now = ensure_utc(self.clock(), "clock").to_pydatetime()
        cfg = load("live_evidence")
        out: list[PollRecord] = []
        round_: list[tuple[str, list[RawDocument], Exception | None]] = []
        for src in self.sources:
            st = self.state[src.source_id]
            if st.disabled:
                if st.last_attempt_at is None:
                    st.last_attempt_at = now
                    out.append(PollRecord(src.source_id, now, "disabled", []))
                continue
            if st.next_poll_at is not None and now < st.next_poll_at:
                continue
            since = (
                st.last_success_at - timedelta(seconds=float(cfg["overlap_s"]))
                if st.last_success_at
                else now - timedelta(minutes=float(cfg["first_lookback_min"]))
            )
            st.polls += 1
            st.last_attempt_at = now
            t0 = self.timer()
            try:
                docs = src.poll(since)
            except Exception as e:  # recorded; the next poll waits for the backoff
                st.failures += 1
                st.consecutive_failures += 1
                st.last_error = f"{type(e).__name__}: {e}"[:500]
                st.next_poll_at = now + _backoff(st.consecutive_failures)
                round_.append((src.source_id, [], e))
                out.append(PollRecord(src.source_id, now, "failed", [], st.last_error))
                continue
            ms = (self.timer() - t0) * 1000.0
            st.latencies_ms.append(ms)
            st.consecutive_failures, st.last_error = 0, None
            st.last_success_at = now
            st.next_poll_at = now + _cadence(src.source_id)
            round_.append((src.source_id, docs, None))
            res: list[IngestResult] = []
            if not self.collect_for:
                done = ensure_utc(self.clock(), "clock").to_pydatetime()
                res = [ingest(self.conn, d, done, self.storage) for d in docs]
                st.docs_new += sum(r.status in ("new", "correction") for r in res)
            out.append(PollRecord(src.source_id, now, "ok", res, latency_ms=ms))
        if self.collect_for and round_:
            runs = self._collect(round_, now)
            out = [
                PollRecord(r.source_id, r.at, r.status, r.results, r.error, r.latency_ms, tuple(runs))
                for r in out
            ]
        return out

    def _collect(
        self, round_: list[tuple[str, list[RawDocument], Exception | None]], now: datetime
    ) -> list[str]:
        from sr.evidence.collection_log import run_collection

        first = now - timedelta(minutes=float(load("live_evidence")["first_lookback_min"]))
        ids = []
        for sec in self.collect_for:
            srcs: list[EvidenceSource] = [_Prefetched(sid, docs, err) for sid, docs, err in round_]
            done = ensure_utc(self.clock(), "clock").to_pydatetime()
            r = run_collection(
                self.conn,
                sec,
                srcs,
                self._window_to.get(sec, first),
                done,
                storage=self.storage,
                now=done,
            )
            self._window_to[sec] = done
            ids.append(r.collection_run_id)
        for sid, docs, err in round_:
            if err is None:
                self.state[sid].docs_fetched += len(docs)
        return ids

    def summary(self) -> dict[str, dict[str, Any]]:
        return {
            k: {
                "polls": s.polls,
                "failures": s.failures,
                "consecutive_failures": s.consecutive_failures,
                "last_success_at": s.last_success_at,
                "last_error": s.last_error,
                "docs_new": s.docs_new,
                "docs_fetched": s.docs_fetched,
                "disabled": s.disabled,
            }
            for k, s in self.state.items()
        }
