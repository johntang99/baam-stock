"""Shared helpers for price series (pd.Series of floats indexed by tz-aware UTC timestamps)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sr.timeguard import assert_not_after, ensure_utc


def checked(series: pd.Series, as_of: datetime, what: str) -> tuple[pd.Series, pd.Timestamp]:
    t = ensure_utc(as_of, "as_of")
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError(f"{what}: index must be a DatetimeIndex")
    assert_not_after(series.index, t, what)
    return series.sort_index(), t


def value_at(series: pd.Series, t: pd.Timestamp) -> float | None:
    """Last observation at or before t."""
    s = series.loc[:t]
    if s.empty or not np.isfinite(s.iloc[-1]):
        return None
    return float(s.iloc[-1])


def return_pct(series: pd.Series, as_of: datetime, minutes: int, what: str = "series") -> float | None:
    s, t = checked(series, as_of, what)
    p1 = value_at(s, t)
    p0 = value_at(s, t - timedelta(minutes=minutes))
    if p0 is None or p1 is None or p0 <= 0:
        return None
    return (p1 / p0 - 1.0) * 100.0
