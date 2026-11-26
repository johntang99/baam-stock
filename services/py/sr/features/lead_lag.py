"""Peer lead-lag inside the basket: each constituent's and SMH's 5/15/30-minute returns (MEMO I-3)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from sr.config import load
from sr.features._series import return_pct


def lead_lag_features(series_by_symbol: dict[str, pd.Series], constituents: list[str],
                      as_of: datetime) -> dict[str, float | None]:
    g = load("features/fs-0.2")["groups"]["lead_lag"]
    out: dict[str, float | None] = {}
    for sym in [*constituents, *g["extra_symbols"]]:
        s = series_by_symbol.get(sym)
        for h in g["horizons_min"]:
            key = f"{sym.lower().lstrip('^')}_ret_{h}m"
            out[key] = None if s is None else return_pct(s, as_of, int(h), sym)
    return out
