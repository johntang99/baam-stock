"""Feature row at publish time (DP 1.14; fs-0.2; OQ-48). The same functions as the dataset build (1.11), so a
published forecast sees exactly what a training row saw: minute mids labelled by minute END, only quotes received
by the publish time, sigma / HAR terms only from windows that had ended.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sr.config import load
from sr.marketdata.quote_rules import evaluate_quotes
from sr.timeguard import LookaheadError, ensure_utc
from sr.train.dataset import features_at, minute_mids, security_of, symbol_of
from sr.train.models.har_vol import har_terms
from sr.train.train import add_derived


def series_for(provider: Any, security_ids: list[str], publish_at: datetime) -> dict[str, pd.Series]:
    """Minute mids per symbol from quotes received by publish_at (the provider refuses anything later)."""
    t = ensure_utc(publish_at, "publish_at")
    start = t - timedelta(days=int(load("forecast")["series_lookback_days"]))
    have = getattr(provider, "security_ids", None)
    ids = [i for i in security_ids if have is None or i in have]
    raw = provider.quotes_1s(ids, start.to_pydatetime(), t.to_pydatetime())
    if not len(raw):
        return {}
    q = evaluate_quotes(raw)
    q = q[q["received_at"] <= t]
    return {k: v[v.index <= t] for k, v in minute_mids(q).items()}


def realised_before(history: pd.DataFrame, publish_at: datetime) -> pd.DataFrame:
    """Windows that had ended by publish_at (sigma / HAR inputs). Raises if `history` is not a realised-window frame."""
    need = {"security_id", "session_date", "t0_ts", "end_ts", "relative_return_pp"}
    if not need <= set(history.columns):
        raise ValueError(f"history needs columns {sorted(need)}")
    t = ensure_utc(publish_at, "publish_at")
    h = history[history["relative_return_pp"].notna() & history["end_ts"].notna()]
    return h[pd.to_datetime(h["end_ts"], utc=True) <= t]


def feature_row(
    series: dict[str, pd.Series],
    security_id: str,
    constituents: list[str],
    publish_at: datetime,
    session_date: Any,
    sigma_hat_pp: float | None,
    history: pd.DataFrame,
) -> pd.DataFrame:
    """One dataset-shaped row: f_* features (+ derived peer means, sigma) and HAR terms."""
    t = ensure_utc(publish_at, "publish_at")
    for k, s in series.items():
        if len(s) and s.index.max() > t:
            raise LookaheadError(f"series {k} has data after publish_at {t.isoformat()}")
    f = features_at(series, symbol_of(security_id), [symbol_of(c) for c in constituents], t.to_pydatetime())
    row = pd.DataFrame(
        [
            {
                "security_id": security_id,
                "session_date": session_date,
                "sigma_hat_pp": sigma_hat_pp,
                **{f"f_{k}": v for k, v in f.items()},
            }
        ]
    )
    row = add_derived(row)
    return har_terms(row, realised_before(history, t.to_pydatetime()))


def reference_ids() -> list[str]:
    return [security_of(s) for s in load("dataset")["reference_symbols"]]
