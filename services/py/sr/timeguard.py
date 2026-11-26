"""Point-in-time guards. Every time-dependent function must refuse data after its as_of (CLAUDE.md, DC §4)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

import pandas as pd


class LookaheadError(RuntimeError):
    """Raised when a computation is handed data stamped after its as_of (DC §4: 回放读取 available_at > T 抛错)."""


class NaiveDatetimeError(ValueError):
    """All datetimes must be timezone-aware (stored/compared in UTC)."""


def ensure_utc(ts: datetime | pd.Timestamp, name: str = "timestamp") -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        raise NaiveDatetimeError(f"{name} must be timezone-aware, got naive {t!r}")
    return t.tz_convert(UTC)


def assert_not_after(
    stamps: Iterable[datetime | pd.Timestamp] | pd.Index | pd.Series,
    as_of: datetime | pd.Timestamp,
    what: str = "data",
) -> None:
    """Raise LookaheadError if any stamp is later than as_of."""
    cutoff = ensure_utc(as_of, "as_of")
    s = pd.Series(
        pd.to_datetime(pd.Index(stamps) if not isinstance(stamps, pd.Series) else stamps, utc=False)
    )
    if s.empty:
        return
    if s.dt.tz is None:
        raise NaiveDatetimeError(f"{what} timestamps must be timezone-aware")
    latest = s.max()
    if latest > cutoff:
        raise LookaheadError(
            f"{what} contains timestamps after as_of: latest={latest.isoformat()} as_of={cutoff.isoformat()}"
        )
