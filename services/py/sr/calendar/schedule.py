"""Daily forecast schedule expansion (sched-0.1, D-43, DC §3.7a)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

from sr.calendar.calendar import ET, TradingCalendar, _hhmm, et_to_utc, get_calendar
from sr.config import load

SlotStatus = Literal["scheduled", "not_scheduled"]


@dataclass(frozen=True)
class Slot:
    slot_id: str
    kind: str
    scheduled_for: datetime  # UTC
    time_et: str  # effective ET wall clock (may differ from config on half days)
    target_ids: tuple[str, ...]
    status: SlotStatus
    schedule_version: str
    note: str = ""
    start_rule: str = field(default="", compare=False)


def schedule_slots(
    d: date, cal: TradingCalendar | None = None, schedule: dict[str, Any] | None = None
) -> list[Slot]:
    """Expand the schedule for session date d. Closed day -> []. Half day -> intraday slots whose 60m window
    would exceed the close are `not_scheduled`; to-close moves to the last scheduled 60m slot; the post-close
    outlook moves to close + offset (13:30 on a 13:00 close)."""
    cal = cal or get_calendar()
    sch = schedule or load("forecast_schedule")
    s = cal.session(d)
    if not s.is_open or s.close_at is None:
        return []
    tgt_cfg = load("targets")
    dur = next(t for t in tgt_cfg["targets"] if t["target_id"] == "regular_60m")["window_rule"][
        "duration_min"
    ]
    tol = tgt_cfg["availability"]["regular_60m_settle_tolerance_s"]
    hdr = sch["half_day_rule"]
    version = sch["schedule_version"]

    raw: list[dict[str, Any]] = []
    for c in sch["slots"]:
        at = et_to_utc(d, _hhmm(c["time_et"]))
        targets = list(c["target_ids"])
        status: SlotStatus = "scheduled"
        note = ""
        if c["kind"] == "intraday" and at + timedelta(minutes=dur, seconds=tol) > s.close_at:
            if hdr.get("skip_if_window_exceeds_close", True):
                status, note = "not_scheduled", "60m window exceeds close (half day)"
        if c["kind"] == "post_close_outlook":
            at = s.close_at + timedelta(minutes=int(hdr["post_close_outlook_offset_min"]))
        raw.append({"c": c, "at": at, "targets": targets, "status": status, "note": note})

    # to_close relocation when its configured slot is not scheduled
    if hdr.get("to_close_moves_to") == "last_60m_slot":
        for r in raw:
            if "regular_to_close" in r["targets"] and r["status"] == "not_scheduled":
                r["targets"].remove("regular_to_close")
                live = [x for x in raw if x["c"]["kind"] == "intraday" and x["status"] == "scheduled"]
                if live:
                    live[-1]["targets"].append("regular_to_close")
                    live[-1]["note"] = "regular_to_close moved here (half day)"
        for r in raw:
            if r["status"] == "not_scheduled":
                r["targets"] = [t for t in r["targets"] if t != "regular_to_close"]

    out = []
    for r in raw:
        out.append(
            Slot(
                slot_id=r["c"]["slot_id"],
                kind=r["c"]["kind"],
                scheduled_for=r["at"],
                time_et=r["at"].astimezone(ET).strftime("%H:%M"),
                target_ids=tuple(r["targets"]),
                status=r["status"],
                schedule_version=version,
                note=r["note"],
                start_rule=r["c"]["start_rule"],
            )
        )
    return out
