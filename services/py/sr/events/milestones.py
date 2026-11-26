"""Event milestones (DC §3.4 event_milestones): scheduled -> occurred | delayed | cancelled."""

from __future__ import annotations

from datetime import datetime

from sr.db import Conn
from sr.ids import new_id
from sr.timeguard import ensure_utc

_ALLOWED = {
    "scheduled": {"occurred", "delayed", "cancelled"},
    "delayed": {"occurred", "cancelled", "delayed"},
    "occurred": set(),
    "cancelled": set(),
}


def add_milestone(
    conn: Conn,
    event_id: str,
    milestone_type: str,
    expected_at: datetime | None = None,
    decision_body: str | None = None,
    evidence_ids: list[str] | None = None,
) -> str:
    mid = new_id("ms")
    conn.execute(
        """insert into event_milestones (milestone_id, event_id, milestone_type, decision_body, expected_at, evidence_ids)
           values (%s,%s,%s,%s,%s,%s)""",
        (
            mid,
            event_id,
            milestone_type,
            decision_body,
            ensure_utc(expected_at, "expected_at").to_pydatetime() if expected_at else None,
            evidence_ids or [],
        ),
    )
    return mid


def set_status(
    conn: Conn,
    milestone_id: str,
    status: str,
    actual_at: datetime | None = None,
    evidence_ids: list[str] | None = None,
) -> None:
    row = conn.execute(
        "select status, evidence_ids from event_milestones where milestone_id = %s", (milestone_id,)
    ).fetchone()
    if row is None:
        raise KeyError(milestone_id)
    if status not in _ALLOWED[row["status"]]:
        raise ValueError(f"milestone {milestone_id}: {row['status']} -> {status} not allowed")
    if status == "occurred" and actual_at is None:
        raise ValueError("occurred milestones need actual_at")
    ids = list(dict.fromkeys([*row["evidence_ids"], *(evidence_ids or [])]))
    conn.execute(
        "update event_milestones set status = %s, actual_at = %s, evidence_ids = %s where milestone_id = %s",
        (
            status,
            ensure_utc(actual_at, "actual_at").to_pydatetime() if actual_at else None,
            ids,
            milestone_id,
        ),
    )
