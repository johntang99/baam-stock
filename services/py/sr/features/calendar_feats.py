"""Time-of-day and calendar features (MEMO I-1)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sr.calendar.calendar import ET, TradingCalendar, get_calendar
from sr.config import load
from sr.timeguard import ensure_utc


def is_triple_witching(d: date) -> bool:
    """Third Friday of March, June, September, December."""
    return d.month in (3, 6, 9, 12) and d.weekday() == 4 and 15 <= d.day <= 21


def calendar_features(
    as_of: datetime, cal: TradingCalendar | None = None
) -> dict[str, float | int | bool | None]:
    cal = cal or get_calendar()
    t = ensure_utc(as_of, "as_of").to_pydatetime()
    d = t.astimezone(ET).date()
    s = cal.session(d)
    rebal = {date.fromisoformat(str(x)) for x in load("features/fs-0.2").get("index_rebalance_dates") or []}
    in_session = (
        s.is_open and s.open_at is not None and s.close_at is not None and s.open_at <= t <= s.close_at
    )
    return {
        "minutes_since_open": (t - s.open_at) / timedelta(minutes=1) if in_session and s.open_at else None,
        "minutes_to_close": (s.close_at - t) / timedelta(minutes=1) if in_session and s.close_at else None,
        "day_of_week": d.weekday(),
        "is_half_day": s.status == "early_close",
        "is_triple_witching": is_triple_witching(d),
        "is_index_rebalance_day": d in rebal,
    }
