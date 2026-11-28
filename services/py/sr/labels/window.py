"""60-minute window label (DC §4; D-05, D-06, D-07, D-18): shared by the dataset build (DP 1.11) and settlement (1.15).

t0  = first sync qualifying quote strictly after the publish time, within `t0_max_wait_s` (else no_sync_start_quote)
end = first sync qualifying quote at or after t0 + duration, within the settle tolerance (else no_sync_end_quote)
relative_return_pp = stock return − basket return (equal weight renormalised over the constituents present, D-06)
A stock halt / LULD pause anywhere in [t0, end] makes the window invalid (`halted`).

`as_of` is when the label is computed: a window that had not ended by then raises LookaheadError.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import pandas as pd

from sr.benchmark.basket import basket_return
from sr.config import load
from sr.marketdata.sync import find_first_sync_qualifying
from sr.timeguard import ensure_utc


@dataclass(frozen=True)
class WindowLabel:
    status: Literal["ok", "invalid"]
    invalid_reason: str | None
    t0_ts: pd.Timestamp | None = None
    end_ts: pd.Timestamp | None = None
    t0_quote_ts: pd.Timestamp | None = None
    stock_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    relative_return_pp: float | None = None
    missing_constituents: tuple[str, ...] = ()


def _between(quotes: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp) -> pd.DataFrame:
    """Rows with a <= ts <= b (a cheap pre-filter; the sync search applies its own exact bounds)."""
    ts = quotes["ts"]
    return quotes[(ts >= a) & (ts <= b)]


def _target(target_id: str) -> dict[str, Any]:
    return next(t for t in load("targets")["targets"] if t["target_id"] == target_id)


def window_label(
    quotes: pd.DataFrame,
    security: str,
    weights: dict[str, float],
    published_at: datetime,
    as_of: datetime | None = None,
    target_id: str = "regular_60m",
) -> WindowLabel:
    """`quotes`: evaluated 1-second quotes (stock + basket) covering the window."""
    rule = _target(target_id)["window_rule"]
    sync = load("quote_rules")["sync"]
    tol_ms = int(sync["tolerance_ms"])
    basket = list(weights)
    wait_s = int(load("dataset")["sample"]["t0_max_wait_s"])
    settle_s = int(rule["settle_tolerance_s"])
    pub = ensure_utc(published_at, "published_at")
    t0 = find_first_sync_qualifying(
        published_at,
        security,
        basket,
        tol_ms,
        wait_s,
        quotes=_between(quotes, pub, pub + pd.Timedelta(seconds=wait_s)),
        as_of=as_of,
        invalid_reason_if_none="no_sync_start_quote",
    )
    if t0.status != "ok" or t0.sample_ts is None or t0.quote is None:
        return WindowLabel("invalid", "no_sync_start_quote")
    target_end = t0.sample_ts + timedelta(minutes=int(rule["duration_min"]))
    end = find_first_sync_qualifying(
        target_end.to_pydatetime(),
        security,
        basket,
        tol_ms,
        settle_s,
        quotes=_between(quotes, target_end, target_end + pd.Timedelta(seconds=settle_s)),
        inclusive=True,
        as_of=as_of,
        invalid_reason_if_none="no_sync_end_quote",
    )
    if end.status != "ok" or end.sample_ts is None or end.quote is None:
        return WindowLabel("invalid", "no_sync_end_quote", t0.sample_ts)
    s = _between(quotes, t0.sample_ts, end.sample_ts)
    s = s[s["security_id"] == security]
    if bool(s["halted"].any()) or bool(s["luld_pause"].any()):
        return WindowLabel("invalid", "halted", t0.sample_ts, end.sample_ts)
    p0, p1 = float(t0.quote["mid"]), float(end.quote["mid"])
    stock = (p1 / p0 - 1.0) * 100.0
    br = basket_return(
        {c: t0.constituent_quotes.get(c, {}).get("mid") for c in basket},
        {c: end.constituent_quotes.get(c, {}).get("mid") for c in basket},
        weights,
    )
    if br.status != "ok" or br.return_pct is None:
        return WindowLabel("invalid", "benchmark_unavailable", t0.sample_ts, end.sample_ts)
    return WindowLabel(
        "ok",
        None,
        t0.sample_ts,
        end.sample_ts,
        ensure_utc(t0.quote["quote_ts"], "quote_ts"),
        stock,
        br.return_pct,
        stock - br.return_pct,
        br.missing,
    )
