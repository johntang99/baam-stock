"""Equal-weight peer basket returns with the pre-registered missing rule (D-06, D-08; DC §3.6)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from sr.config import load


@dataclass(frozen=True)
class BasketReturn:
    status: Literal["ok", "benchmark_unavailable"]
    return_pct: float | None
    missing: tuple[str, ...]
    weights_used: Mapping[str, float]


def _ok(x: float | None) -> bool:
    return x is not None and math.isfinite(x) and x > 0


def basket_return(
    start_prices: Mapping[str, float | None],
    end_prices: Mapping[str, float | None],
    weights: Mapping[str, float],
    max_missing: int | None = None,
) -> BasketReturn:
    """Weighted mean of constituent simple returns, in percent.

    A constituent is missing if its start or end price is absent/invalid. If more than `max_missing`
    (default from config, D-06 = 1) are missing the benchmark is unavailable; otherwise the remaining
    weights are renormalised to sum to 1 (equal weight stays equal weight).
    """
    mm = int(load("benchmarks")["semis_peer_v1"]["max_missing_constituents"]) if max_missing is None else max_missing
    missing = tuple(c for c in weights if not (_ok(start_prices.get(c)) and _ok(end_prices.get(c))))
    if len(missing) > mm:
        return BasketReturn("benchmark_unavailable", None, missing, {})
    avail = {c: w for c, w in weights.items() if c not in missing}
    total = sum(avail.values())
    if total <= 0:
        return BasketReturn("benchmark_unavailable", None, missing, {})
    used = {c: w / total for c, w in avail.items()}
    ret = sum(w * (float(end_prices[c]) / float(start_prices[c]) - 1.0) for c, w in used.items())  # type: ignore[arg-type]
    return BasketReturn("ok", ret * 100.0, missing, used)


def relative_return_pp(stock_return_pct: float, basket: BasketReturn) -> float | None:
    """relative_return_pp = stock − basket (percentage points); None when the basket is unavailable."""
    if basket.status != "ok" or basket.return_pct is None:
        return None
    return stock_return_pct - basket.return_pct


def equal_weights(constituents: list[str]) -> dict[str, float]:
    return {c: 1.0 / len(constituents) for c in constituents}
