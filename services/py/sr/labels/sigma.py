"""sigma-0.1 (D-09): forecast std-dev (pp) of the same-window relative return, made at publish time.

EWMA over the last `lookback_sessions` trading days of realised relative returns of windows that started in
the same time-of-day bucket, half-life `ewma_half_life_days` trading days, zero-mean (RiskMetrics style):
    sigma = sqrt( sum_i w_i r_i^2 / sum_i w_i ),  w_i = 0.5 ** (age_i / half_life)
age_i = trading sessions between the observation's session and the publish session (yesterday = 1).
Only windows that had ENDED by as_of may be used; handing in anything later raises LookaheadError.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from sr.calendar.calendar import ET, TradingCalendar, get_calendar
from sr.config import load
from sr.timeguard import assert_not_after, ensure_utc


@dataclass(frozen=True)
class SigmaEstimate:
    sigma_hat_pp: float | None
    n_obs: int
    sigma_model_version: str
    reason: str | None = None   # 'insufficient_data' when None


def time_bucket(ts: pd.Timestamp, bucket_minutes: int) -> int:
    et = ts.tz_convert(ET)
    return (et.hour * 60 + et.minute) // bucket_minutes


def estimate_sigma(
    history: pd.DataFrame,
    window_start: datetime,
    as_of: datetime,
    cal: TradingCalendar | None = None,
    cfg: dict[str, Any] | None = None,
) -> SigmaEstimate:
    """history columns: window_start, window_end (UTC), relative_return_pp (realised, settled)."""
    c = cfg or load("sigma")
    cal = cal or get_calendar()
    asof = ensure_utc(as_of, "as_of")
    ws = ensure_utc(window_start, "window_start")
    if not history.empty:
        assert_not_after(history["window_end"], asof, "sigma history (window_end)")
    version = c["sigma_model_version"]
    if history.empty:
        return SigmaEstimate(None, 0, version, "insufficient_data")

    bm = int(c["bucket_minutes"])
    target_bucket = time_bucket(ws, bm)
    target_session = ws.tz_convert(ET).date()
    h = history.copy()
    h["session"] = h["window_start"].dt.tz_convert(ET).dt.date
    h["bucket"] = [time_bucket(t, bm) for t in h["window_start"]]
    h = h[(h["bucket"] == target_bucket) & (h["session"] < target_session)]
    if h.empty:
        return SigmaEstimate(None, 0, version, "insufficient_data")
    h["age"] = [cal.sessions_between(s, target_session) for s in h["session"]]
    h = h[(h["age"] >= 1) & (h["age"] <= int(c["lookback_sessions"]))]
    if len(h) < int(c["min_observations"]):
        return SigmaEstimate(None, len(h), version, "insufficient_data")
    w = 0.5 ** (h["age"] / float(c["ewma_half_life_days"]))
    var = float((w * h["relative_return_pp"] ** 2).sum() / w.sum())
    return SigmaEstimate(math.sqrt(var), len(h), version)
