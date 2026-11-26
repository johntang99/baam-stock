"""XNYS trading calendar = exchange_calendars + config/calendar_overrides.yaml (D-04).

All returned instants are UTC; wall-clock inputs are America/New_York.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import cache
from typing import Literal
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from sr.config import load
from sr.timeguard import ensure_utc

ET = ZoneInfo("America/New_York")
SessionStatus = Literal["open", "early_close", "closed"]


@dataclass(frozen=True)
class Session:
    exchange: str
    session_date: date
    status: SessionStatus
    open_at: datetime | None     # UTC
    close_at: datetime | None    # UTC
    source: str
    calendar_version: str

    @property
    def is_open(self) -> bool:
        return self.status != "closed"


def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def et_to_utc(d: date, t: time) -> datetime:
    """America/New_York wall clock -> UTC (DST-aware)."""
    return datetime.combine(d, t, tzinfo=ET).astimezone(UTC)


class TradingCalendar:
    def __init__(self, exchange: str = "XNYS") -> None:
        cfg = load("calendar_overrides")
        self.exchange = exchange
        self.calendar_version: str = cfg["calendar_version"]
        rng = cfg.get("range") or {}
        self._base = xcals.get_calendar(exchange, start=rng.get("start"), end=rng.get("end"))
        self._src = f"exchange_calendars:{exchange}@{xcals.__version__}"
        self._regular_close = _hhmm(cfg["regular_close_et"])
        self._early_close = _hhmm(cfg["early_close_et"])
        self._regular_open = _hhmm(cfg["regular_open_et"])
        self._overrides: dict[date, dict[str, str]] = {
            date.fromisoformat(str(o["date"])): o for o in (cfg.get("overrides") or [])
        }

    def session(self, d: date) -> Session:
        if isinstance(d, datetime):
            raise TypeError("session() takes a date (session_date), not a datetime")
        ov = self._overrides.get(d)
        if ov is not None:
            status: SessionStatus = ov["status"]  # type: ignore[assignment]
            src = f"override:{ov.get('ticket', 'n/a')}"
            if status == "closed":
                return Session(self.exchange, d, "closed", None, None, src, self.calendar_version)
            close_t = _hhmm(ov["close_et"]) if ov.get("close_et") else (
                self._early_close if status == "early_close" else self._regular_close)
            return Session(self.exchange, d, status, et_to_utc(d, self._regular_open), et_to_utc(d, close_t), src,
                           self.calendar_version)
        ts = pd.Timestamp(d)
        if not self._base.is_session(ts):
            return Session(self.exchange, d, "closed", None, None, self._src, self.calendar_version)
        open_at = self._base.session_open(ts).to_pydatetime().astimezone(UTC)
        close_at = self._base.session_close(ts).to_pydatetime().astimezone(UTC)
        regular_close = et_to_utc(d, self._regular_close)
        status = "early_close" if close_at < regular_close else "open"
        return Session(self.exchange, d, status, open_at, close_at, self._src, self.calendar_version)

    def sessions(self, start: date, end: date) -> list[Session]:
        """All calendar days in [start, end] that are weekdays or open (weekends listed only if overridden open)."""
        out = []
        d = start
        while d <= end:
            s = self.session(d)
            if s.is_open or d.weekday() < 5:
                out.append(s)
            d += timedelta(days=1)
        return out

    def open_sessions(self, start: date, end: date) -> list[Session]:
        return [s for s in self.sessions(start, end) if s.is_open]

    def next_open_session_after(self, ts: datetime) -> Session:
        """First open session whose open_at is strictly after ts."""
        t = ensure_utc(ts, "ts").to_pydatetime()
        d = t.astimezone(ET).date()
        for _ in range(30):
            s = self.session(d)
            if s.is_open and s.open_at is not None and s.open_at > t:
                return s
            d += timedelta(days=1)
        raise RuntimeError(f"no open session within 30 days after {t.isoformat()}")

    def previous_open_session(self, d: date) -> Session:
        x = d - timedelta(days=1)
        for _ in range(30):
            s = self.session(x)
            if s.is_open:
                return s
            x -= timedelta(days=1)
        raise RuntimeError(f"no open session within 30 days before {d}")

    def sessions_between(self, earlier: date, later: date) -> int:
        """Number of open sessions in (earlier, later] — trading-day age of `earlier` seen from `later`."""
        if earlier >= later:
            return 0
        return len(self.open_sessions(earlier + timedelta(days=1), later))

    def session_for_instant(self, ts: datetime) -> Session:
        t = ensure_utc(ts, "ts").to_pydatetime()
        return self.session(t.astimezone(ET).date())


@cache
def get_calendar(exchange: str = "XNYS") -> TradingCalendar:
    return TradingCalendar(exchange)
