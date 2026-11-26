"""Realised-volatility regime (MEMO I-4): 5/30/390-minute realised vol, overnight gap, opening range.

Realised vol over N minutes = sqrt(sum of squared 1-minute log returns of the last N minutes) in percent
(not annualised). Inputs are 1-minute regular-session mids; earlier sessions count toward 390m.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sr.calendar.calendar import ET, TradingCalendar, get_calendar
from sr.config import load
from sr.features._series import checked, value_at


def realized_vol_pct(mids_1m: pd.Series, as_of: datetime, minutes: int) -> float | None:
    s, t = checked(mids_1m, as_of, "mids_1m")
    s = s.loc[:t].dropna()
    if len(s) < minutes + 1:
        return None
    r = np.diff(np.log(s.to_numpy()[-(minutes + 1) :]))
    return float(math.sqrt(float(np.sum(r**2))) * 100.0)


def overnight_gap_pct(
    mids_1m: pd.Series, as_of: datetime, cal: TradingCalendar | None = None
) -> float | None:
    """Today's first regular-session mid vs the previous session's last mid."""
    cal = cal or get_calendar()
    s, t = checked(mids_1m, as_of, "mids_1m")
    sess = cal.session(t.tz_convert(ET).date())
    if not sess.is_open or sess.open_at is None or t < sess.open_at:
        return None
    prev = cal.previous_open_session(sess.session_date)
    today = s.loc[sess.open_at : t]
    before = s.loc[: prev.close_at] if prev.close_at else s.iloc[0:0]
    if today.empty or before.empty:
        return None
    return (float(today.iloc[0]) / float(before.iloc[-1]) - 1.0) * 100.0


def opening_range_pct(
    mids_1m: pd.Series, as_of: datetime, minutes: int = 30, cal: TradingCalendar | None = None
) -> float | None:
    """(high − low) / open of the first `minutes` of the session; None until that range is complete."""
    cal = cal or get_calendar()
    s, t = checked(mids_1m, as_of, "mids_1m")
    sess = cal.session(t.tz_convert(ET).date())
    if not sess.is_open or sess.open_at is None:
        return None
    end = sess.open_at + timedelta(minutes=minutes)
    if t < end:
        return None
    w = s.loc[sess.open_at : end - timedelta(microseconds=1)]
    if w.empty:
        return None
    return (float(w.max()) - float(w.min())) / float(w.iloc[0]) * 100.0


def vol_regime_features(
    mids_1m: pd.Series, as_of: datetime, cal: TradingCalendar | None = None
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for f in load("features/fs-0.2")["groups"]["vol_regime"]:
        n = f["name"]
        if n.startswith("rv_"):
            out[n] = realized_vol_pct(mids_1m, as_of, int(f["minutes"]))
        elif n == "overnight_gap_pct":
            out[n] = overnight_gap_pct(mids_1m, as_of, cal)
        elif n == "opening_range_pct":
            out[n] = opening_range_pct(mids_1m, as_of, int(f["minutes"]), cal)
    return out


__all__ = ["opening_range_pct", "overnight_gap_pct", "realized_vol_pct", "value_at", "vol_regime_features"]
