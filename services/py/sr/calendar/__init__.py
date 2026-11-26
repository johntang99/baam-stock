"""Trading calendar, window availability and daily forecast schedule (D-04, D-10, D-18, D-43)."""

from sr.calendar.calendar import Session, TradingCalendar, get_calendar
from sr.calendar.schedule import Slot, schedule_slots
from sr.calendar.windows import Availability, is_target_available, next_regular_session

__all__ = [
    "Availability",
    "Session",
    "Slot",
    "TradingCalendar",
    "get_calendar",
    "is_target_available",
    "next_regular_session",
    "schedule_slots",
    "session",
]


def session(d):  # type: ignore[no-untyped-def]
    """Convenience: XNYS session for a date (DP P0-B `session(date)`)."""
    return get_calendar().session(d)
