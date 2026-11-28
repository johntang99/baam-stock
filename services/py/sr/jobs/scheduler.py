"""Live scheduler: turns the session calendar into queued jobs (DP 2.02, 2.24 core; D-17, D-43; OQ-58).

- `enqueue_session()`: for each security, one `build_snapshot` job per scheduled 5-minute / session-check trigger
  (D-17) and, optionally, one `run_forecast` job per sched-0.1 slot (D-43). Keys are deterministic, so running the
  scheduler twice for a day queues nothing new.
- `enqueue_event_snapshot()` / `enqueue_move_snapshot()`: snapshot jobs from events and market-move rules.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sr.calendar import get_calendar
from sr.calendar.schedule import schedule_slots
from sr.db import Conn
from sr.jobs.queue import enqueue
from sr.snapshot.builder import schedule
from sr.snapshot.triggers import cooldown_bucket
from sr.timeguard import ensure_utc


def _iso(t: datetime) -> str:
    return ensure_utc(t, "t").isoformat()


def snapshot_payload(
    security_id: str, trigger_type: str, trigger_ref: str | None, as_of: datetime
) -> dict[str, Any]:
    return {
        "security_id": security_id,
        "trigger_type": trigger_type,
        "trigger_ref": trigger_ref,
        "as_of": _iso(as_of),
    }


def enqueue_session(
    conn: Conn, session_date: date, security_ids: list[str], slots: bool = True
) -> dict[str, int]:
    s = get_calendar().session(session_date)
    n = {"build_snapshot": 0, "run_forecast": 0, "existing": 0}
    for sec in security_ids:
        for t in schedule(s):
            _, made = enqueue(
                conn,
                "build_snapshot",
                snapshot_payload(sec, t.trigger_type, t.trigger_ref, t.analysis_as_of),
                f"snap|{sec}|{t.trigger_type}|{_iso(t.analysis_as_of)}",
                t.analysis_as_of,
            )
            n["build_snapshot" if made else "existing"] += 1
        if not slots:
            continue
        for sl in schedule_slots(session_date):
            if sl.status != "scheduled" or not sl.target_ids:
                continue
            _, made = enqueue(
                conn,
                "run_forecast",
                {
                    "security_id": sec,
                    "slot_id": sl.slot_id,
                    "targets": list(sl.target_ids),
                    "scheduled_for": _iso(sl.scheduled_for),
                },
                f"slot|{sec}|{sl.slot_id}|{session_date.isoformat()}",
                sl.scheduled_for,
            )
            n["run_forecast" if made else "existing"] += 1
    return n


def enqueue_event_snapshot(conn: Conn, security_id: str, event_id: str, as_of: datetime) -> tuple[str, bool]:
    t = ensure_utc(as_of, "as_of").floor("1s").to_pydatetime()
    return enqueue(
        conn,
        "build_snapshot",
        snapshot_payload(security_id, "event", event_id, t),
        f"snap|{security_id}|event|{event_id}|{_iso(t)}",
        t,
    )


def enqueue_move_snapshot(conn: Conn, security_id: str, rule_id: str, as_of: datetime) -> tuple[str, bool]:
    t = ensure_utc(as_of, "as_of").floor("1s").to_pydatetime()
    return enqueue(
        conn,
        "build_snapshot",
        snapshot_payload(security_id, "market_move", rule_id, t),
        f"snap|{security_id}|move|{rule_id}|{cooldown_bucket(t)}",
        t,
    )
