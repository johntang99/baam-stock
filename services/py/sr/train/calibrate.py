"""Probability calibration for 3-class forecasts (DP 1.12; OQ-46): isotonic one-vs-rest or Platt, renormalised.

Fitted on the calibration split only. Parameters are plain lists so a calibrator round-trips through JSON and
applies with numpy alone (the published model must be reproducible from its artifact).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

_EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    q = np.clip(p, _EPS, 1 - _EPS)
    return np.asarray(np.log(q / (1 - q)))


def _renorm(p: np.ndarray) -> np.ndarray:
    s = p.sum(axis=1, keepdims=True)
    k = p.shape[1]
    return np.where(s > 0, p / np.where(s > 0, s, 1.0), 1.0 / k)


@dataclass
class Calibrator:
    method: Literal["isotonic", "platt", "identity"]
    params: list[dict[str, Any]] = field(default_factory=list)  # one entry per class

    @classmethod
    def fit(cls, probs: np.ndarray, y: np.ndarray, isotonic_min_rows: int) -> Calibrator:
        """probs (n × K) uncalibrated; y class indices 0..K-1."""
        n, k = probs.shape
        if n == 0:
            return cls("identity")
        method: Literal["isotonic", "platt"] = "isotonic" if n >= isotonic_min_rows else "platt"
        params = []
        for c in range(k):
            target = (y == c).astype(float)
            if method == "isotonic":
                iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(probs[:, c], target)
                params.append({"x": iso.X_thresholds_.tolist(), "y": iso.y_thresholds_.tolist()})
            else:
                if target.min() == target.max():  # one class only: keep the raw probability
                    params.append({"a": 1.0, "b": 0.0})
                    continue
                lr = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(probs[:, c]).reshape(-1, 1), target)
                params.append({"a": float(lr.coef_[0, 0]), "b": float(lr.intercept_[0])})
        return cls(method, params)

    def transform(self, probs: np.ndarray) -> np.ndarray:
        if self.method == "identity":
            return _renorm(probs.copy())
        out = np.empty_like(probs, dtype=float)
        for c, p in enumerate(self.params):
            if self.method == "isotonic":
                out[:, c] = np.interp(probs[:, c], p["x"], p["y"])
            else:
                out[:, c] = 1.0 / (1.0 + np.exp(-(p["a"] * _logit(probs[:, c]) + p["b"])))
        return _renorm(out)

    def to_dict(self) -> dict[str, Any]:
        return {"method": self.method, "params": self.params}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Calibrator:
        return cls(d["method"], list(d["params"]))
