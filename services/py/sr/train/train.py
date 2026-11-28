"""First training run (DP 1.12; D-24, D-30; AC-16; OQ-46).

market_logit = L2 multinomial logistic regression on ~20 market features (train split), calibrated on the
calibration split (isotonic one-vs-rest, or Platt when the split is small). References (D-30): class_frequency,
always_flat, persistence. Metrics per subset (train / calibration / validation) and group (all, security):
brier, log_loss, hit_rate, ece, coverage, n_effective (trading days) and BSS vs each reference with a trading-day
block-bootstrap 95 % CI. Same dataset + config + seed -> identical metrics.

The run is refused when the dataset failed its availability check or any row's t0 is not after its sample time
(nothing stamped after the forecast time may reach training).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from sr.config import load, repo_root
from sr.db import Conn, jsonb
from sr.eval.metrics import CLASSES
from sr.ids import new_id
from sr.labels.thresholds import classify
from sr.train.calibrate import Calibrator

REF_TICKERS = {"qqq", "spy", "smh", "vix"}


class AvailabilityError(RuntimeError):
    """The dataset could let information from after the forecast time into training."""


@dataclass
class MarketLogit:
    features: list[str]
    medians: list[float]
    means: list[float]
    stds: list[float]
    coef: list[list[float]]
    intercept: list[float]
    classes: list[str]
    calibrator: Calibrator | None = None
    hyperparams: dict[str, Any] = field(default_factory=dict)

    def raw_proba(self, X: np.ndarray) -> np.ndarray:
        Z = (np.where(np.isnan(X), np.asarray(self.medians), X) - np.asarray(self.means)) / np.asarray(
            self.stds
        )
        s = Z @ np.asarray(self.coef).T + np.asarray(self.intercept)
        s -= s.max(axis=1, keepdims=True)
        e = np.exp(s)
        return np.asarray(e / e.sum(axis=1, keepdims=True))

    def proba(self, X: np.ndarray) -> np.ndarray:
        p = self.raw_proba(X)
        return self.calibrator.transform(p) if self.calibrator else p

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_family": "market_logit",
            "features": self.features,
            "medians": self.medians,
            "means": self.means,
            "stds": self.stds,
            "coef": self.coef,
            "intercept": self.intercept,
            "classes": self.classes,
            "calibrator": self.calibrator.to_dict() if self.calibrator else None,
            "hyperparams": self.hyperparams,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MarketLogit:
        cal = Calibrator.from_dict(d["calibrator"]) if d.get("calibrator") else None
        return cls(
            d["features"],
            d["medians"],
            d["means"],
            d["stds"],
            d["coef"],
            d["intercept"],
            d["classes"],
            cal,
            d["hyperparams"],
        )


# ---------------------------------------------------------------- data
def add_derived(frame: pd.DataFrame) -> pd.DataFrame:
    """peer_mean_ret_{h}m = mean of the fs-0.2 constituent lead-lag returns at horizon h (NaN if none)."""
    f = frame.copy()
    for h in (5, 15, 30):
        cols = [
            c
            for c in f.columns
            if (m := re.fullmatch(rf"f_([a-z0-9]+)_ret_{h}m", c)) and m.group(1) not in REF_TICKERS
        ]
        f[f"f_peer_mean_ret_{h}m"] = f[cols].astype(float).mean(axis=1) if cols else np.nan
    f["f_sigma_hat_pp"] = f["sigma_hat_pp"] if "sigma_hat_pp" in f else np.nan
    return f


def design(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    cols = [f"f_{n}" for n in features]
    missing = [c for c in cols if c not in frame.columns]
    X = frame.reindex(columns=cols).astype(float).to_numpy()
    if missing and len(frame):
        X[:, [cols.index(c) for c in missing]] = np.nan
    return X


def check_availability(dataset_row: dict[str, Any], frame: pd.DataFrame) -> None:
    if not dataset_row.get("availability_check_passed"):
        raise AvailabilityError("dataset availability check did not pass")
    kept = frame[frame["exclusion"].isna()]
    bad = kept[~(pd.to_datetime(kept["t0_quote_ts"], utc=True) > pd.to_datetime(kept["sample_ts"], utc=True))]
    if len(bad):
        raise AvailabilityError(f"{len(bad)} row(s) have a t0 quote not after their sample time")


def persistence_labels(rows: pd.DataFrame, history: pd.DataFrame) -> list[str | None]:
    """Per row: the same security's latest window (from `history`, any row with a realised window) that had ended
    by the row's sample time, classified with the row's own threshold; None if there is none (OQ-46)."""
    if rows.empty:
        return []
    left = rows[["security_id", "sample_ts", "threshold_pp"]].reset_index(names="_i")
    left["sample_ts"] = pd.to_datetime(left["sample_ts"], utc=True)
    h = history[history["relative_return_pp"].notna() & history["end_ts"].notna()][
        ["security_id", "end_ts", "relative_return_pp"]
    ].copy()
    h["end_ts"] = pd.to_datetime(h["end_ts"], utc=True)
    m = pd.merge_asof(
        left.sort_values("sample_ts"),
        h.sort_values("end_ts"),
        left_on="sample_ts",
        right_on="end_ts",
        by="security_id",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("_i")
    return [
        None if pd.isna(r) else classify(float(r), float(t))
        for r, t in zip(m["relative_return_pp"], m["threshold_pp"], strict=True)
    ]


# ---------------------------------------------------------------- metrics
def _onehot(y: np.ndarray, k: int) -> np.ndarray:
    o = np.zeros((len(y), k))
    o[np.arange(len(y)), y] = 1.0
    return o


def brier_rows(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.asarray(((p - _onehot(y, p.shape[1])) ** 2).sum(axis=1))


def ece(p: np.ndarray, y: np.ndarray, bins: int) -> float:
    conf = p.max(axis=1)
    acc = (p.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(acc[m].mean() - conf[m].mean())
    return float(total)


def bss_ci(
    bm: np.ndarray, br: np.ndarray, days: np.ndarray, seed: int, n: int, level: float
) -> tuple[float, float, float]:
    """BSS = 1 − ΣBrier_model / ΣBrier_ref, CI by resampling whole trading days (D-30)."""
    keys, inv = np.unique(days, return_inverse=True)
    sm = np.bincount(inv, weights=bm, minlength=len(keys))
    sr_ = np.bincount(inv, weights=br, minlength=len(keys))
    est = 1.0 - sm.sum() / sr_.sum()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(keys), size=(n, len(keys)))
    num, den = sm[pick].sum(axis=1), sr_[pick].sum(axis=1)
    samples = 1.0 - num / np.where(den > 0, den, np.nan)
    a = (1 - level) / 2
    return float(est), float(np.nanquantile(samples, a)), float(np.nanquantile(samples, 1 - a))


@dataclass(frozen=True)
class Metric:
    subset: str
    group_key: str
    metric: str
    value: float
    reference_model: str | None = None
    ci95_low: float | None = None
    ci95_high: float | None = None
    denominator: int | None = None


def evaluate(
    model: MarketLogit,
    kept: pd.DataFrame,
    class_freq: dict[str, float],
    seed: int,
    target_id: str,
    history: pd.DataFrame | None = None,
) -> list[Metric]:
    cfg, ev = load("train"), load("eval")["bootstrap"]
    classes = list(CLASSES)
    y_all = kept["label"].map({c: i for i, c in enumerate(classes)}).to_numpy()
    p_all = model.proba(design(kept, model.features))
    pers = persistence_labels(kept, kept if history is None else history)
    freq = np.asarray([class_freq[c] for c in classes])
    refs = {
        "class_frequency": np.tile(freq, (len(kept), 1)),
        "always_flat": np.tile(_onehot(np.asarray([classes.index("flat")]), 3)[0], (len(kept), 1)),
        "persistence": np.asarray(
            [_onehot(np.asarray([classes.index(c)]), 3)[0] if c else freq for c in pers]
        ).reshape(-1, 3)
        if len(kept)
        else np.zeros((0, 3)),
    }
    out: list[Metric] = []
    groups: list[tuple[str, pd.Series]] = [("all", pd.Series(True, index=kept.index))]
    groups += [(f"security:{s}", kept["security_id"] == s) for s in sorted(kept["security_id"].unique())]
    for subset in cfg["metrics"]["subsets"]:
        in_s = kept["split"] == subset
        for gkey, gmask in groups:
            m = (in_s & gmask).to_numpy()
            n = int(m.sum())
            if n == 0:
                continue
            p, y = p_all[m], y_all[m]
            days = kept.loc[m, "session_date"].astype(str).to_numpy()
            b = brier_rows(p, y)
            ll = float(-np.mean(np.log(np.clip(p[np.arange(n), y], 1e-15, 1.0))))
            out += [
                Metric(subset, gkey, "brier", float(b.mean()), denominator=n),
                Metric(subset, gkey, "log_loss", ll, denominator=n),
                Metric(subset, gkey, "hit_rate", float((p.argmax(axis=1) == y).mean()), denominator=n),
                Metric(subset, gkey, "ece", ece(p, y, int(cfg["metrics"]["ece_bins"])), denominator=n),
                Metric(subset, gkey, "coverage", 1.0, denominator=n),  # every eligible row gets a forecast
                Metric(subset, gkey, "n_effective", float(len(set(days))), denominator=n),
            ]
            for ri, ref in enumerate(cfg["references"]):
                br = brier_rows(refs[ref][m], y)
                if br.sum() <= 0:
                    continue
                est, lo, hi = bss_ci(b, br, days, seed + ri, int(ev["n_resamples"]), float(ev["ci"]))
                out.append(Metric(subset, gkey, "brier_skill_score", est, ref, lo, hi, n))
    return out


# ---------------------------------------------------------------- fit
def fit_market_logit(kept: pd.DataFrame, seed: int) -> MarketLogit:
    cfg = load("train")
    mc = cfg["market_logit"]
    feats = list(mc["features"])
    tr = kept[kept["split"] == "train"]
    if tr["label"].nunique() < 2:
        raise ValueError("the train split needs at least two label classes")
    X = design(tr, feats)
    med = np.nanmedian(np.where(np.isnan(X).all(axis=0), 0.0, X), axis=0) if len(X) else np.zeros(len(feats))
    med = np.where(np.isnan(med), 0.0, med)
    Xi = np.where(np.isnan(X), med, X)
    mu, sd = Xi.mean(axis=0), Xi.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    classes = list(CLASSES)
    y = tr["label"].map({c: i for i, c in enumerate(classes)}).to_numpy()
    lr = LogisticRegression(C=float(mc["C"]), max_iter=int(mc["max_iter"]), random_state=seed)
    lr.fit((Xi - mu) / sd, y)
    # sklearn orders coefficients by the classes it saw; expand to all three (an unseen class gets a very low score).
    # With two classes sklearn fits one binary row w, b: softmax scores (0, w·x + b) reproduce its probabilities.
    coef = np.zeros((3, len(feats)))
    inter = np.full(3, -50.0)
    seen = [int(c) for c in lr.classes_]
    if len(seen) == 2:
        coef[seen[0]], inter[seen[0]] = 0.0, 0.0
        coef[seen[1]], inter[seen[1]] = lr.coef_[0], lr.intercept_[0]
    else:
        for row, c in enumerate(seen):
            coef[c], inter[c] = lr.coef_[row], lr.intercept_[row]
    return MarketLogit(
        feats,
        med.tolist(),
        mu.tolist(),
        sd.tolist(),
        coef.tolist(),
        inter.tolist(),
        classes,
        hyperparams={
            "C": float(mc["C"]),
            "penalty": "l2",
            "solver": "lbfgs",
            "max_iter": int(mc["max_iter"]),
            "seed": seed,
        },
    )


def calibrate(model: MarketLogit, kept: pd.DataFrame) -> MarketLogit:
    """Fit the calibrator on the calibration split only (identity when it is empty)."""
    cal = kept[kept["split"] == "calibration"]
    classes = model.classes
    yc = cal["label"].map({c: i for i, c in enumerate(classes)}).to_numpy()
    raw = model.raw_proba(design(cal, model.features)) if len(cal) else np.zeros((0, len(classes)))
    model.calibrator = Calibrator.fit(raw, yc, int(load("train")["calibration"]["isotonic_min_rows"]))
    return model


@dataclass(frozen=True)
class TrainOutput:
    model: MarketLogit
    class_frequency: dict[str, float]
    metrics: list[Metric]


def train_and_evaluate(
    frame: pd.DataFrame, seed: int, target_id: str = "regular_60m", on_stage: Any = None
) -> TrainOutput:
    """Pure: dataset frame (with split / exclusion columns) -> model + metrics. `on_stage(status)` reports progress."""
    kept = add_derived(
        frame[
            frame["exclusion"].isna() & frame["split"].isin(["train", "calibration", "validation", "holdout"])
        ]
    )
    kept = kept.reset_index(drop=True)
    model = fit_market_logit(kept, seed)
    if on_stage:
        on_stage("calibrating")
    model = calibrate(model, kept)
    if on_stage:
        on_stage("evaluating")
    tr = kept[kept["split"] == "train"]["label"]
    freq = {c: float((tr == c).mean()) for c in CLASSES}
    return TrainOutput(model, freq, evaluate(model, kept, freq, seed, target_id, history=frame))


# ---------------------------------------------------------------- run (DB + artifacts)
def metrics_models(target_id: str, scope: dict[str, Any]) -> list[dict[str, Any]]:
    """The model_versions rows a run registers (status candidate; contract-0.7.3)."""
    if target_id == "regular_60m":
        out, paths = scope["out"], scope["paths"]
        cal = out.model.calibrator.method if out.model.calibrator else "identity"
        cal_version = f"cal_{cal}_{scope['run_id']}"
        common = {"coefficients_path": paths["market_logit"], "artifact_sha256": paths["sha256"]}
        return [
            {
                "model_version_id": paths["model_version_id"],
                "model_family": "market_logit",
                "features": out.model.features,
                "hyperparams": out.model.hyperparams,
                "calibration_version": cal_version,
                **common,
            },
            {
                "model_version_id": paths["baseline_model_version_id"],
                "model_family": "class_frequency",
                "features": [],
                "hyperparams": {"class_frequency": out.class_frequency},
                "calibration_version": "none",
                **common,
            },
        ]
    mv, paths = scope["mv"], scope["paths"]
    return [
        {
            "model_version_id": paths["har_vol_model_version_id"],
            "model_family": "har_vol",
            "features": ["har_rv_d", "har_rv_w", "har_rv_m"],
            "hyperparams": {"lags": load("move")["har"]["lags_sessions"]},
            "calibration_version": "ratio_calibration",
            "coefficients_path": paths["har_vol"],
            "artifact_sha256": paths["har_vol_sha256"],
        },
        {
            "model_version_id": paths["move_quantile_model_version_id"],
            "model_family": "gbdt",
            "features": mv.model.features,
            "hyperparams": dict(load("move")["gbdt"]),
            "calibration_version": "conformal" if mv.model.shifts else "none",
            "coefficients_path": paths["move_quantile"],
            "artifact_sha256": paths["move_quantile_sha256"],
        },
    ]


def register_models(
    conn: Conn, run_id: str, target_id: str, paths: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    for r in rows:
        conn.execute(
            """insert into model_versions (model_version_id, training_run_id, target_id, model_family, param_layers, scope,
                   features, hyperparams, coefficients_path, calibration_version, artifact_sha256, status)
               values (%s, %s, %s::target_id, %s::model_family, 'market', %s, %s, %s, %s, %s, %s, 'candidate')""",
            (
                r["model_version_id"],
                run_id,
                target_id,
                r["model_family"],
                jsonb({"securities": [], "sectors": ["semis"]}),
                r["features"],
                jsonb(r["hyperparams"]),
                r["coefficients_path"],
                r["calibration_version"],
                r["artifact_sha256"],
            ),
        )


@dataclass(frozen=True)
class TrainingResult:
    training_run_id: str
    status: str
    metrics: list[Metric]
    artifact_paths: dict[str, Any]
    reused: bool = False


def _code_version() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=repo_root()
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_dataset(conn: Conn, dataset_version_id: str) -> tuple[dict[str, Any], pd.DataFrame]:
    row = conn.execute(
        "select * from training_dataset_versions where dataset_version_id = %s", (dataset_version_id,)
    ).fetchone()
    if row is None:
        raise KeyError(dataset_version_id)
    mp = Path(row["manifest_path"])
    mp = mp if mp.is_absolute() else repo_root() / mp
    return dict(row), pd.read_parquet(mp.parent / "rows.parquet")


def _set(conn: Conn, run_id: str, **kv: Any) -> None:
    cols = ", ".join(f"{k} = %s" for k in kv)
    vals = [jsonb(v) if k in ("error", "artifact_paths") else v for k, v in kv.items()]
    conn.execute(f"update training_runs set {cols} where training_run_id = %s", [*vals, run_id])


def run_training(
    conn: Conn,
    dataset_version_id: str,
    trigger: str = "manual",
    seed: int | None = None,
    now: datetime | None = None,
    out_dir: Path | None = None,
    parent_model_version_id: str | None = None,
) -> TrainingResult:
    cfg = load("train")
    seed = int(cfg["random_seed"]) if seed is None else seed
    clock = now or datetime.now(UTC)
    code = _code_version()
    config_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    key = f"{dataset_version_id}|{config_hash}|{seed}|{code}"
    prior = conn.execute("select * from training_runs where idempotency_key = %s", (key,)).fetchone()
    if prior is not None:  # same inputs: return the existing run, never train twice
        ms = conn.execute(
            "select * from training_run_metrics where training_run_id = %s order by seq",
            (prior["training_run_id"],),
        ).fetchall()
        metrics = [
            Metric(
                m["subset"],
                m["group_key"],
                m["metric"],
                float(m["value"]),
                m["reference_model"],
                None if m["ci95_low"] is None else float(m["ci95_low"]),
                None if m["ci95_high"] is None else float(m["ci95_high"]),
                m["denominator"],
            )
            for m in ms
        ]
        return TrainingResult(
            prior["training_run_id"], prior["status"], metrics, prior["artifact_paths"], reused=True
        )
    run_id = new_id("tr")
    conn.execute(
        """insert into training_runs (training_run_id, dataset_version_id, trigger, parent_model_version_id, code_version,
                                      config_hash, random_seed, status, stage, started_at, idempotency_key)
           values (%s, %s, %s::training_trigger, %s, %s, %s, %s, 'building_dataset', 'load_dataset', %s, %s)""",
        (run_id, dataset_version_id, trigger, parent_model_version_id, code, config_hash, seed, clock, key),
    )
    try:
        ds_row, frame = load_dataset(conn, dataset_version_id)
        check_availability(ds_row, frame)
        target_id = str(ds_row["target_id"])
        d = (out_dir or repo_root() / cfg["output_dir"]) / run_id
        d.mkdir(parents=True, exist_ok=True)
        _set(conn, run_id, status="training", stage=target_id)
        if target_id == "regular_60m":
            out = train_and_evaluate(
                frame, seed, target_id, on_stage=lambda st: _set(conn, run_id, status=st, stage=st)
            )
            metrics = out.metrics
            mdl_id = new_id("mdl")
            art = {
                "model_version_id": mdl_id,
                "target_id": target_id,
                "dataset_version_id": dataset_version_id,
                "training_run_id": run_id,
                "train_version": cfg["version"],
                **out.model.to_dict(),
                "references": {"class_frequency": out.class_frequency},
            }
            p = d / "market_logit.json"
            p.write_text(json.dumps(art, indent=2, sort_keys=True) + "\n")
            paths: dict[str, Any] = {
                "market_logit": str(p),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "model_version_id": mdl_id,
                "baseline_model_version_id": new_id(
                    "mdl"
                ),  # class_frequency, registered alongside (DC prediction_runs)
            }
        elif target_id == "regular_60m_move":
            import pickle

            from sr.train.move import train_and_evaluate_move

            _set(conn, run_id, status="calibrating", stage="har_vol+gbdt")
            mv = train_and_evaluate_move(frame, seed)
            _set(conn, run_id, status="evaluating", stage="metrics")
            metrics = mv.metrics
            har_id, q_id = new_id("mdl"), new_id("mdl")
            ph = d / "har_vol.json"
            ph.write_text(
                json.dumps(
                    {
                        "model_version_id": har_id,
                        "target_id": target_id,
                        "dataset_version_id": dataset_version_id,
                        "training_run_id": run_id,
                        "move_version": load("move")["version"],
                        **mv.har.to_dict(),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            pq_ = d / "move_quantile.pkl"
            pq_.write_bytes(
                pickle.dumps({"model_version_id": q_id, "model_family": "gbdt", "model": mv.model})
            )
            paths = {
                "har_vol": str(ph),
                "har_vol_sha256": hashlib.sha256(ph.read_bytes()).hexdigest(),
                "har_vol_model_version_id": har_id,
                "move_quantile": str(pq_),
                "move_quantile_sha256": hashlib.sha256(pq_.read_bytes()).hexdigest(),
                "move_quantile_model_version_id": q_id,
            }
        else:
            raise ValueError(f"no training recipe for target {target_id}")
        register_models(conn, run_id, target_id, paths, metrics_models(target_id, locals()))
        recorded = now or datetime.now(UTC)
        for seq, m in enumerate(metrics):
            conn.execute(
                """insert into training_run_metrics (training_run_id, seq, stage, iteration, subset, target_id, group_key,
                       metric, reference_model, ci95_low, ci95_high, value, denominator, recorded_at)
                   values (%s, %s, 'evaluating', null, %s::metric_subset, %s::target_id, %s, %s::metric_name,
                           %s::reference_model, %s, %s, %s, %s, %s)""",
                (
                    run_id,
                    seq,
                    m.subset,
                    target_id,
                    m.group_key,
                    m.metric,
                    m.reference_model,
                    m.ci95_low,
                    m.ci95_high,
                    m.value,
                    m.denominator,
                    recorded,
                ),
            )
        _set(
            conn,
            run_id,
            status="completed",
            stage="done",
            finished_at=now or datetime.now(UTC),
            artifact_paths=paths,
        )
        return TrainingResult(run_id, "completed", metrics, paths)
    except AvailabilityError as e:
        _set(
            conn,
            run_id,
            status="failed",
            stage="availability_check",
            finished_at=now or datetime.now(UTC),
            error={"code": "availability_check_failed", "message": str(e)},
        )
        raise
    except Exception as e:
        _set(
            conn,
            run_id,
            status="failed",
            finished_at=now or datetime.now(UTC),
            error={"code": type(e).__name__, "message": str(e)[:500]},
        )
        raise
