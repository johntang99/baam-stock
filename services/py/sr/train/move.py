"""Training + evaluation for regular_60m_move (DP 1.13; D-29; AC-27 training part; OQ-47).

har_vol baseline and the GBDT quantile model are fitted on the train split and calibrated on the calibration
split. Metrics per subset and group: pinball_loss (mean of p50/p80/p90), interval_coverage and interval_width per
quantile (`group_key` "<group>|p80"), n_effective, and the comparison with HAR as `pinball_loss` with
`reference_model = har_vol` holding (model − HAR) and a trading-day block-bootstrap CI. HAR's own metrics are
recorded with `group_key` "har_vol:<group>".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from sr.config import load
from sr.train.models.har_vol import HAR_TERMS, HarVol, har_terms
from sr.train.models.move_quantile import MoveQuantile
from sr.train.train import Metric, add_derived


def pinball_rows(tau: float, q: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Vectorised sr.eval.metrics.pinball_loss (same formula; a test keeps them equal)."""
    e = y - q
    return np.asarray(np.maximum(tau * e, (tau - 1.0) * e))


def _pinball(qs: dict[str, np.ndarray], y: np.ndarray, levels: dict[str, float]) -> np.ndarray:
    """Per-row mean pinball loss over the quantiles."""
    return np.asarray(np.mean([pinball_rows(levels[q], qs[q], y) for q in levels], axis=0))


def diff_ci(d: np.ndarray, days: np.ndarray, seed: int, n: int, level: float) -> tuple[float, float, float]:
    """Mean per-row difference, CI by resampling whole trading days (mean of resampled rows, D-30)."""
    keys, inv = np.unique(days, return_inverse=True)
    s = np.bincount(inv, weights=d, minlength=len(keys))
    c = np.bincount(inv, minlength=len(keys)).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(keys), size=(n, len(keys)))
    samples = s[pick].sum(axis=1) / c[pick].sum(axis=1)
    a = (1 - level) / 2
    return float(d.mean()), float(np.quantile(samples, a)), float(np.quantile(samples, 1 - a))


@dataclass(frozen=True)
class MoveOutput:
    har: HarVol
    model: MoveQuantile
    metrics: list[Metric]


def _quantile_metrics(
    prefix: str,
    subset: str,
    qs: dict[str, np.ndarray],
    y: np.ndarray,
    levels: dict[str, float],
    days: np.ndarray,
) -> list[Metric]:
    n = len(y)
    out = [
        Metric(subset, prefix, "pinball_loss", float(_pinball(qs, y, levels).mean()), denominator=n),
        Metric(subset, prefix, "n_effective", float(len(set(days))), denominator=n),
    ]
    for q in levels:
        out.append(
            Metric(subset, f"{prefix}|{q}", "interval_coverage", float((y <= qs[q]).mean()), denominator=n)
        )
        out.append(Metric(subset, f"{prefix}|{q}", "interval_width", float(np.mean(qs[q])), denominator=n))
    return out


def train_and_evaluate_move(frame: pd.DataFrame, seed: int) -> MoveOutput:
    cfg, ev = load("move"), load("eval")["bootstrap"]
    levels = {str(k): float(v) for k, v in cfg["quantiles"].items()}
    kept = frame[frame["exclusion"].isna() & frame["label_value"].notna()]
    kept = har_terms(add_derived(kept), frame).reset_index(drop=True)
    tr, cal = kept[kept["split"] == "train"], kept[kept["split"] == "calibration"]
    if len(tr) < 10:
        raise ValueError("the train split is too small for the move models")
    har = HarVol.fit(tr, cal, levels)
    feats = [*HAR_TERMS, *(f"f_{n}" for n in load("train")["market_logit"]["features"])]
    model = MoveQuantile.fit(tr, cal, feats, levels, seed)

    metrics: list[Metric] = []
    groups: list[tuple[str, pd.Series]] = [("all", pd.Series(True, index=kept.index))]
    groups += [(f"security:{s}", kept["security_id"] == s) for s in sorted(kept["security_id"].unique())]
    for subset in cfg["metrics"]["subsets"]:
        for gkey, gm in groups:
            m = ((kept["split"] == subset) & gm).to_numpy()
            if not m.any():
                continue
            rows, y = kept[m], kept.loc[m, "label_value"].astype(float).to_numpy()
            days = kept.loc[m, "session_date"].astype(str).to_numpy()
            qm, qh = model.predict(rows), har.quantiles(rows)
            metrics += _quantile_metrics(gkey, subset, qm, y, levels, days)
            metrics += _quantile_metrics(f"har_vol:{gkey}", subset, qh, y, levels, days)
            d = _pinball(qm, y, levels) - _pinball(qh, y, levels)
            est, lo, hi = diff_ci(d, days, seed, int(ev["n_resamples"]), float(ev["ci"]))
            metrics.append(Metric(subset, gkey, "pinball_loss", est, "har_vol", lo, hi, len(y)))
    return MoveOutput(har, model, metrics)


def artifacts(out: MoveOutput) -> dict[str, Any]:
    return {
        "har_vol": out.har.to_dict(),
        "move_quantile": {
            "features": out.model.features,
            "quantiles": out.model.quantiles,
            "shifts": out.model.shifts,
        },
    }
