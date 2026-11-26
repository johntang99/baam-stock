"""Vol-scaled three-class thresholds (D-09): threshold_pp = k × sigma_hat_pp, locked at publish time.

Labels: relative_return_pp >  threshold -> outperform
        relative_return_pp < -threshold -> underperform
        otherwise (boundary included)   -> flat
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sr.config import load

# Comparisons are made after rounding to 1e-9 pp so that a value equal to the threshold (e.g. 0.15 vs
# 0.25 × 0.60) is "flat" regardless of binary floating-point representation.
_EPS_DECIMALS = 9

DirectionClass = Literal["outperform", "flat", "underperform"]


@dataclass(frozen=True)
class LockedThreshold:
    sigma_model_version: str
    sigma_hat_pp: float
    threshold_k: float
    threshold_pp: float

    def as_locked(self) -> dict[str, object]:
        """Fields written into predictions.locked (DC §3.7)."""
        return {"sigma_model_version": self.sigma_model_version, "sigma_hat_pp": self.sigma_hat_pp,
                "threshold_k": self.threshold_k, "threshold_pp": self.threshold_pp}


@dataclass(frozen=True)
class Abstain:
    abstain_reason: str   # DC abstain_reason enum


def threshold_pp(sigma_hat_pp: float, k: float) -> float:
    if sigma_hat_pp < 0 or k < 0:
        raise ValueError("sigma_hat_pp and k must be non-negative")
    return round(k * sigma_hat_pp, _EPS_DECIMALS)


def lock_threshold(sigma_hat_pp: float | None, k: float | None = None,
                   sigma_model_version: str | None = None) -> LockedThreshold | Abstain:
    """Freeze the threshold at publish time; missing sigma -> abstain insufficient_data (D-09)."""
    cfg = load("sigma")
    k = float(cfg["threshold_k"]) if k is None else k
    ver = sigma_model_version or cfg["sigma_model_version"]
    if sigma_hat_pp is None or sigma_hat_pp != sigma_hat_pp or sigma_hat_pp <= 0:
        return Abstain("insufficient_data")
    return LockedThreshold(ver, float(sigma_hat_pp), float(k), threshold_pp(float(sigma_hat_pp), float(k)))


def classify(relative_return_pp: float, threshold: float) -> DirectionClass:
    r = round(relative_return_pp, _EPS_DECIMALS)
    t = round(threshold, _EPS_DECIMALS)
    if r > t:
        return "outperform"
    if r < -t:
        return "underperform"
    return "flat"
