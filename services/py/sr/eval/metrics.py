"""Scoring (D-30, DC §8.1): three-class Brier, hit rate, Brier Skill Score vs three references, pinball loss."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

import numpy as np

CLASSES = ("outperform", "flat", "underperform")


def _check_probs(p: Mapping[str, float], classes: Sequence[str]) -> None:
    if set(p) != set(classes):
        raise ValueError(f"probabilities keys {sorted(p)} != classes {sorted(classes)}")
    if abs(sum(p.values()) - 1.0) > 1e-6:
        raise ValueError(f"probabilities sum to {sum(p.values())}, not 1 (DC §1)")


def brier(probs: Mapping[str, float], outcome: str, classes: Sequence[str] = CLASSES) -> float:
    """Multi-class Brier: sum_c (p_c − 1[c = outcome])^2. Uniform 1/3 -> 0.6667; DC §8.1 example -> 0.5798."""
    _check_probs(probs, classes)
    if outcome not in classes:
        raise ValueError(f"outcome {outcome!r} not in classes")
    return float(sum((probs[c] - (1.0 if c == outcome else 0.0)) ** 2 for c in classes))


def predicted_class(probs: Mapping[str, float], classes: Sequence[str] = CLASSES) -> str:
    """argmax; ties broken by class order (deterministic)."""
    return max(classes, key=lambda c: (probs[c], -classes.index(c)))


def hit(probs: Mapping[str, float], outcome: str, classes: Sequence[str] = CLASSES) -> bool:
    return predicted_class(probs, classes) == outcome


def hit_rate(prob_list: Sequence[Mapping[str, float]], outcomes: Sequence[str]) -> float:
    if not outcomes:
        raise ValueError("empty sample")
    return float(np.mean([hit(p, o) for p, o in zip(prob_list, outcomes, strict=True)]))


def mean_brier(prob_list: Sequence[Mapping[str, float]], outcomes: Sequence[str]) -> float:
    if not outcomes:
        raise ValueError("empty sample")
    return float(np.mean([brier(p, o) for p, o in zip(prob_list, outcomes, strict=True)]))


def brier_skill_score(brier_model: float, brier_reference: float) -> float:
    """BSS = 1 − Brier / Brier_ref (D-30). AC-28: 0.641 vs 0.666 -> 0.0375."""
    if brier_reference <= 0:
        raise ValueError("reference Brier must be > 0")
    return 1.0 - brier_model / brier_reference


# --- reference forecasts (D-30) -------------------------------------------------------------------------
def class_frequency_forecast(train_outcomes: Sequence[str], classes: Sequence[str] = CLASSES) -> dict[str, float]:
    """Constant forecast = class frequencies of the (earlier) training labels."""
    if not train_outcomes:
        raise ValueError("class_frequency needs training labels")
    cnt = Counter(train_outcomes)
    n = len(train_outcomes)
    return {c: cnt.get(c, 0) / n for c in classes}


def always_flat_forecast(classes: Sequence[str] = CLASSES) -> dict[str, float]:
    return {c: (1.0 if c == "flat" else 0.0) for c in classes}


def persistence_forecast(previous_outcome: str, classes: Sequence[str] = CLASSES) -> dict[str, float]:
    """The previous 60-minute relative-return direction continues (one-hot)."""
    if previous_outcome not in classes:
        raise ValueError(f"unknown class {previous_outcome!r}")
    return {c: (1.0 if c == previous_outcome else 0.0) for c in classes}


# --- quantile scoring (regular_60m_move, D-29) -----------------------------------------------------------
def pinball_loss(tau: float, q: float, y: float) -> float:
    """max(τ(y − q), (τ − 1)(y − q)). DC §8.1: y=0.24, q50=0.31 -> 0.035; q80=0.58 -> 0.068; q90=0.77 -> 0.053."""
    if not 0 < tau < 1:
        raise ValueError("tau must be in (0, 1)")
    d = y - q
    return max(tau * d, (tau - 1.0) * d)


QUANTILE_TAUS = {"p10": 0.10, "p50": 0.50, "p80": 0.80, "p90": 0.90}


def pinball_by_quantile(quantiles: Mapping[str, float], y: float) -> dict[str, float]:
    return {k: pinball_loss(QUANTILE_TAUS[k], v, y) for k, v in quantiles.items() if k in QUANTILE_TAUS}


def quantile_hits(quantiles: Mapping[str, float], y: float) -> dict[str, bool]:
    """y <= q_k for each upper quantile (used for empirical coverage)."""
    return {k: y <= v for k, v in quantiles.items() if k in QUANTILE_TAUS}


def coverage(hits: Sequence[bool]) -> float:
    if not hits:
        raise ValueError("empty sample")
    return float(np.mean(hits))
