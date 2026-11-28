"""HAR-style expected-move baseline for regular_60m_move (DP 1.13; D-29; OQ-47).

RV_d / RV_w / RV_m = mean |relative return| (pp) of a security's windows in the previous 1 / 5 / 22 sessions — only
sessions before the row's own session, so nothing from the forecast day leaks in. Scale:
    log(|rel| + c) = b0 + b_d log RV_d + b_w log RV_w + b_m log RV_m        (OLS on the train split)
Quantile q = exp(prediction) × r_q, where r_q is the q-th quantile of |rel| / scale on the calibration split.
Everything is plain lists, so the model round-trips through JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from sr.config import load

HAR_TERMS = ("har_rv_d", "har_rv_w", "har_rv_m")


def har_terms(rows: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Add har_rv_d / _w / _m to `rows` from `history` (any rows with a realised window), earlier sessions only."""
    lags = load("move")["har"]["lags_sessions"]
    out = rows.copy()
    h = history[history["relative_return_pp"].notna()]
    daily = (
        h.assign(a=h["relative_return_pp"].abs())
        .groupby(["security_id", "session_date"])["a"]
        .agg(["sum", "count"])
        .reset_index()
        .sort_values(["security_id", "session_date"])
    )
    secs = out["security_id"].to_numpy()
    days = out["session_date"].to_numpy()
    for name, n in (("har_rv_d", int(lags["d"])), ("har_rv_w", int(lags["w"])), ("har_rv_m", int(lags["m"]))):
        vals = np.full(len(out), np.nan)
        for sec, g in daily.groupby("security_id"):
            dates = g["session_date"].to_numpy()
            csum, ccnt = np.cumsum(g["sum"].to_numpy()), np.cumsum(g["count"].to_numpy())
            for pos in np.flatnonzero(secs == sec):
                j = int(np.searchsorted(dates, days[pos], side="left")) - 1  # last session strictly before
                if j < 0:
                    continue
                i0 = j - n  # window = sessions (j-n, j]
                s = csum[j] - (csum[i0] if i0 >= 0 else 0.0)
                c = ccnt[j] - (ccnt[i0] if i0 >= 0 else 0)
                vals[pos] = s / c if c else np.nan
        out[name] = vals
    return out


@dataclass
class HarVol:
    coef: list[float]  # b0, b_d, b_w, b_m
    medians: list[float]  # log-term medians on train (missing inputs)
    ratios: dict[str, float] = field(default_factory=dict)  # q name -> multiplier on the scale
    offset: float = 0.01

    def _logs(self, rows: pd.DataFrame) -> np.ndarray:
        X = np.log(rows[list(HAR_TERMS)].astype(float).to_numpy() + self.offset)
        return np.where(np.isnan(X), np.asarray(self.medians), X)

    def scale(self, rows: pd.DataFrame) -> np.ndarray:
        X = self._logs(rows)
        return np.asarray(np.exp(self.coef[0] + X @ np.asarray(self.coef[1:])))

    def quantiles(self, rows: pd.DataFrame) -> dict[str, np.ndarray]:
        s = self.scale(rows)
        return {q: s * r for q, r in self.ratios.items()}

    @classmethod
    def fit(cls, train: pd.DataFrame, calib: pd.DataFrame, qs: dict[str, float]) -> HarVol:
        off = float(load("move")["har"]["log_offset_pp"])
        X = np.log(train[list(HAR_TERMS)].astype(float).to_numpy() + off)
        med = np.nanmedian(np.where(np.isnan(X).all(axis=0), 0.0, X), axis=0)
        med = np.where(np.isnan(med), 0.0, med)
        X = np.where(np.isnan(X), med, X)
        y = np.log(train["label_value"].astype(float).to_numpy() + off)
        A = np.column_stack([np.ones(len(X)), X])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        m = cls(coef.tolist(), med.tolist(), {}, off)
        base = calib if len(calib) else train  # no calibration rows: fall back to train ratios
        r = base["label_value"].astype(float).to_numpy() / m.scale(base)
        m.ratios = {q: float(np.quantile(r, p)) for q, p in qs.items()}
        return m

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_family": "har_vol",
            "coef": self.coef,
            "medians": self.medians,
            "ratios": self.ratios,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HarVol:
        return cls(list(d["coef"]), list(d["medians"]), dict(d["ratios"]), float(d["offset"]))
