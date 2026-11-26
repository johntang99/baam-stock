"""Target window availability at publish time (D-18, D-28, D-10; DC §4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sr.calendar.calendar import Session, TradingCalendar, get_calendar
from sr.config import load
from sr.timeguard import ensure_utc

INTRADAY_60M = {"regular_60m", "regular_60m_move"}


@dataclass(frozen=True)
class Availability:
    target_id: str
    available: bool
    abstain_reason: str | None     # DC abstain_reason enum when not available
    session: Session | None        # session the window falls in
    window_end_at: datetime | None  # latest possible window end (UTC), when known
    detail: str


def _params() -> tuple[int, int, int]:
    cfg = load("targets")
    av = cfg["availability"]
    dur = next(t for t in cfg["targets"] if t["target_id"] == "regular_60m")["window_rule"]["duration_min"]
    return int(dur), int(av["regular_60m_settle_tolerance_s"]), int(av["to_close_min_remaining_min"])


def is_target_available(target_id: str, published_at: datetime, cal: TradingCalendar | None = None) -> Availability:
    """Can a forecast for `target_id` be published at `published_at`?

    - regular_60m / regular_60m_move: regular session in progress and published_at + 60m + 30s <= close (D-18).
      Outside the regular session -> market_closed (D-28: no pre/post-market intraday forecasts).
    - regular_to_close: regular session in progress and close - published_at >= 15 min (inclusive, OQ-11).
    - next_regular_session: always available; window = first open session with open after published_at.
    The window start uses published_at as a proxy for t0 (t0 >= published_at), see OQ-12.
    """
    cal = cal or get_calendar()
    t = ensure_utc(published_at, "published_at").to_pydatetime()
    dur_min, tol_s, min_remaining = _params()

    if target_id == "next_regular_session":
        s = next_regular_session(t, cal)
        return Availability(target_id, True, None, s, s.close_at, "next open session after publish")

    if target_id not in INTRADAY_60M and target_id != "regular_to_close":
        raise ValueError(f"availability rule not defined for target_id={target_id!r} in Phase 0")

    s = cal.session_for_instant(t)
    if not s.is_open or s.open_at is None or s.close_at is None or not (s.open_at <= t < s.close_at):
        return Availability(target_id, False, "market_closed", s if s.is_open else None, None,
                            "published outside the regular session")
    if target_id in INTRADAY_60M:
        end = t + timedelta(minutes=dur_min)
        if end + timedelta(seconds=tol_s) <= s.close_at:
            return Availability(target_id, True, None, s, end, "t0+60m+30s <= close")
        return Availability(target_id, False, "window_insufficient", s, None, "t0+60m+30s > close")
    remaining = s.close_at - t
    if remaining >= timedelta(minutes=min_remaining):
        return Availability(target_id, True, None, s, s.close_at, f"{remaining} to close >= {min_remaining}m")
    return Availability(target_id, False, "window_insufficient", s, None, f"{remaining} to close < {min_remaining}m")


def next_regular_session(published_at: datetime, cal: TradingCalendar | None = None) -> Session:
    """The next regular session whose open is strictly after published_at (Saturday -> Monday; 08:30 -> same day)."""
    cal = cal or get_calendar()
    return cal.next_open_session_after(published_at)
