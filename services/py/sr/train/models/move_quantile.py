"""GBDT quantile model for regular_60m_move (DP 1.13; D-29; OQ-47).

One HistGradientBoostingRegressor(loss="quantile") per quantile on the HAR terms + market features (NaN handled
natively), seeded. Split-conformal: on the calibration split each quantile is shifted by the empirical quantile of
(y − prediction) so that it covers its nominal level there; quantiles are then sorted so they never cross and
floored at 0 (the target is an absolute move).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from sr.config import load


@dataclass
class MoveQuantile:
    features: list[str]
    quantiles: dict[str, float]
    models: dict[str, HistGradientBoostingRegressor] = field(default_factory=dict)
    shifts: dict[str, float] = field(default_factory=dict)

    def _X(self, rows: pd.DataFrame) -> np.ndarray:
        return rows.reindex(columns=self.features).astype(float).to_numpy()

    def raw(self, rows: pd.DataFrame) -> dict[str, np.ndarray]:
        X = self._X(rows)
        return {q: np.asarray(m.predict(X)) for q, m in self.models.items()}

    def predict(self, rows: pd.DataFrame) -> dict[str, np.ndarray]:
        r = self.raw(rows)
        names = sorted(self.quantiles, key=lambda q: self.quantiles[q])
        M = np.column_stack([r[q] + self.shifts.get(q, 0.0) for q in names])
        M = np.maximum(np.sort(M, axis=1), 0.0)  # no crossing; |move| >= 0
        return {q: M[:, i] for i, q in enumerate(names)}

    @classmethod
    def fit(
        cls, train: pd.DataFrame, calib: pd.DataFrame, features: list[str], qs: dict[str, float], seed: int
    ) -> MoveQuantile:
        g = load("move")["gbdt"]
        m = cls(features, dict(qs))
        X, y = m._X(train), train["label_value"].astype(float).to_numpy()
        for q, a in qs.items():
            reg = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=a,
                max_iter=int(g["max_iter"]),
                learning_rate=float(g["learning_rate"]),
                max_leaf_nodes=int(g["max_leaf_nodes"]),
                min_samples_leaf=int(g["min_samples_leaf"]),
                random_state=seed,
            )
            m.models[q] = reg.fit(X, y)
        if load("move")["conformal"] and len(calib):
            yc = calib["label_value"].astype(float).to_numpy()
            raw = m.raw(calib)
            m.shifts = {q: float(np.quantile(yc - raw[q], a)) for q, a in qs.items()}
        return m
