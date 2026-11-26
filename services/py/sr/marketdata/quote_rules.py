"""Qualifying quote rules qr-0.1 (D-05, D-12; DC §3.3).

Input: a 1-second reference-quote layer, one row per (security_id, ts) with columns
  ts (sample second, UTC), security_id, quote_ts (exchange/SIP time of the NBBO in effect, UTC),
  received_at (UTC), bid, ask, last, halted (bool), luld_pause (bool).
Output adds: mid, spread_bp, age_s, median_spread_bp_20m, quality_flags (list[str]), is_qualifying.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from sr.config import load

REQUIRED_COLUMNS = ("ts", "security_id", "quote_ts", "received_at", "bid", "ask", "halted", "luld_pause")


@dataclass(frozen=True)
class QuoteRules:
    version: str
    max_spread_bp: float
    max_spread_vs_median_mult: float
    median_window_min: int
    max_quote_age_s: float
    delayed_threshold_s: float
    exclude_halted: bool
    exclude_luld_pause: bool

    @classmethod
    def from_config(cls, cfg: dict[str, Any] | None = None) -> QuoteRules:
        c = cfg or load("quote_rules")
        q = c["qualifying"]
        if c.get("fallback_to_last_trade"):
            raise ValueError("qr-0.1 forbids falling back to last trade (D-05)")
        return cls(
            version=c["quote_rule_version"], max_spread_bp=float(q["max_spread_bp"]),
            max_spread_vs_median_mult=float(q["max_spread_vs_median_mult"]),
            median_window_min=int(q["median_spread_window_min"]), max_quote_age_s=float(q["max_quote_age_s"]),
            delayed_threshold_s=float(c["delayed_threshold_s"]), exclude_halted=bool(q["exclude_halted"]),
            exclude_luld_pause=bool(q["exclude_luld_pause"]),
        )


def evaluate_quotes(df: pd.DataFrame, rules: QuoteRules | None = None) -> pd.DataFrame:
    """Apply qr-0.1 to every row. The 20-minute median spread is trailing (rows with ts <= current ts only)."""
    rules = rules or QuoteRules.from_config()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"quote frame missing columns {missing}")
    out = df.sort_values(["security_id", "ts"]).reset_index(drop=True).copy()
    bid, ask = out["bid"].astype(float), out["ask"].astype(float)
    valid_book = (bid > 0) & (ask > bid)
    out["mid"] = np.where(valid_book, (bid + ask) / 2, np.nan)
    out["spread_bp"] = np.where(valid_book, (ask - bid) / ((bid + ask) / 2) * 1e4, np.nan)
    out["age_s"] = (out["ts"] - out["quote_ts"]).dt.total_seconds()

    med = (
        out.set_index("ts").groupby("security_id")["spread_bp"]
        .rolling(f"{rules.median_window_min}min", min_periods=1).median()
    )
    out["median_spread_bp_20m"] = med.reset_index(drop=True).to_numpy()

    crossed = ~valid_book & (bid > 0) & (ask > 0)
    wide = valid_book & (
        (out["spread_bp"] > rules.max_spread_bp)
        | (out["spread_bp"] > rules.max_spread_vs_median_mult * out["median_spread_bp_20m"])
    )
    stale = out["age_s"] > rules.max_quote_age_s
    halted = out["halted"].astype(bool)
    luld = out["luld_pause"].astype(bool)
    delayed = (out["received_at"] - out["quote_ts"]).dt.total_seconds() > rules.delayed_threshold_s

    flags = []
    for row in zip(stale, wide, halted, luld, crossed, delayed, strict=True):
        flags.append([n for n, on in zip(("stale", "wide_spread", "halted", "luld_pause", "crossed", "delayed"), row,
                                         strict=True) if on])
    out["quality_flags"] = flags
    qualifying = valid_book & ~wide & ~stale
    if rules.exclude_halted:
        qualifying &= ~halted
    if rules.exclude_luld_pause:
        qualifying &= ~luld
    out["is_qualifying"] = qualifying.to_numpy()
    out["quote_rule_version"] = rules.version
    return out
