"""Day-block bootstrap (D-30, MP §7.1): resample whole trading days with replacement, fixed seed.

Overlapping 60-minute windows on the same day are not independent, so a day is the resampling unit.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass

import numpy as np

from sr.config import load


@dataclass(frozen=True)
class BootstrapResult:
    estimate: float
    ci_low: float
    ci_high: float
    n_resamples: int
    n_blocks: int
    seed: int
    samples: np.ndarray


def _blocks(day_keys: Sequence[Hashable]) -> list[np.ndarray]:
    order: dict[Hashable, list[int]] = {}
    for i, k in enumerate(day_keys):
        order.setdefault(k, []).append(i)
    return [np.asarray(v) for v in order.values()]


def resample_indices(day_keys: Sequence[Hashable], rng: np.random.Generator) -> np.ndarray:
    """One bootstrap draw: pick len(days) days with replacement and return all indices of each picked day."""
    blocks = _blocks(day_keys)
    pick = rng.integers(0, len(blocks), size=len(blocks))
    return np.concatenate([blocks[j] for j in pick])


def block_bootstrap(
    values: Sequence[float] | np.ndarray,
    day_keys: Sequence[Hashable],
    seed: int,
    stat: Callable[[np.ndarray], float] = lambda x: float(np.mean(x)),
    n_resamples: int | None = None,
    ci: float | None = None,
) -> BootstrapResult:
    cfg = load("eval")["bootstrap"]
    n = int(cfg["n_resamples"]) if n_resamples is None else n_resamples
    level = float(cfg["ci"]) if ci is None else ci
    v = np.asarray(values, dtype=float)
    if len(v) != len(day_keys) or len(v) == 0:
        raise ValueError("values and day_keys must be non-empty and the same length")
    rng = np.random.default_rng(seed)
    samples = np.empty(n)
    for i in range(n):
        samples[i] = stat(v[resample_indices(day_keys, rng)])
    a = (1 - level) / 2
    return BootstrapResult(stat(v), float(np.quantile(samples, a)), float(np.quantile(samples, 1 - a)), n,
                           len(_blocks(day_keys)), seed, samples)


def paired_block_bootstrap(candidate: Sequence[float], comparator: Sequence[float], day_keys: Sequence[Hashable],
                           seed: int, n_resamples: int | None = None) -> BootstrapResult:
    """CI of mean(candidate − comparator) on the common sample (e.g. per-prediction Brier)."""
    d = np.asarray(candidate, dtype=float) - np.asarray(comparator, dtype=float)
    return block_bootstrap(d, day_keys, seed, n_resamples=n_resamples)
