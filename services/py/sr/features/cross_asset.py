"""Cross-asset proxies: QQQ / SPY returns, ^VIX level and change (MEMO I-2)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from sr.config import load
from sr.features._series import checked, return_pct, value_at


def cross_asset_features(series_by_symbol: dict[str, pd.Series], as_of: datetime) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for f in load("features/fs-0.2")["groups"]["cross_asset"]:
        s = series_by_symbol.get(f["symbol"])
        if s is None:
            out[f["name"]] = None
            continue
        if f["name"] == "vix_level":
            ss, t = checked(s, as_of, f["symbol"])
            out[f["name"]] = value_at(ss, t)
        elif f["name"].startswith("vix_change"):
            ss, t = checked(s, as_of, f["symbol"])
            now, before = value_at(ss, t), value_at(ss, t - pd.Timedelta(minutes=f["minutes"]))
            out[f["name"]] = None if now is None or before is None else now - before  # VIX points
        else:
            out[f["name"]] = return_pct(s, as_of, int(f["minutes"]), f["symbol"])
    return out
