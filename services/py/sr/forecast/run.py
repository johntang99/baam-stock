"""Inference for one security snapshot (DP 1.14; AC-13, AC-27; D-09, D-18, D-23, D-41, D-43; OQ-48).

For each target (regular_60m, regular_60m_move) one prediction_runs row + one prediction, published atomically:
  readiness / market state / data quality / D-18 availability / publish deadline / sigma -> abstain with the DC
  reason, or a forecast: market_logit probabilities (calibrated) + edge vs class_frequency, or gbdt move quantiles;
  locked versions, sampling rule and primary flag (D-23, D-43), validity (D-41), display tier (live -> public).
Models are loaded from model_versions and their artifacts are checked against the registered SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import sr
from sr.calendar import get_calendar, is_target_available
from sr.calendar.schedule import schedule_slots
from sr.config import load, repo_root
from sr.db import Conn
from sr.eval.metrics import CLASSES
from sr.forecast.features import feature_row, realised_before, reference_ids, series_for
from sr.forecast.publish import Published, publish
from sr.ids import new_id
from sr.labels.sigma import estimate_sigma
from sr.labels.thresholds import Abstain, lock_threshold
from sr.snapshot.builder import benchmark_version
from sr.timeguard import ensure_utc
from sr.train.models.har_vol import HarVol
from sr.train.models.move_quantile import MoveQuantile
from sr.train.train import MarketLogit, design


class ArtifactMismatch(RuntimeError):
    """A model artifact on disk does not match the SHA-256 registered in model_versions."""


@dataclass
class LoadedModels:
    direction: MarketLogit
    direction_id: str
    direction_status: str
    calibration_version: str
    baseline_id: str
    class_frequency: dict[str, float]
    move: MoveQuantile
    move_id: str
    move_status: str
    har: HarVol
    har_id: str


def _artifact(row: dict[str, Any]) -> bytes:
    p = Path(row["coefficients_path"])
    data = p.read_bytes()
    if hashlib.sha256(data).hexdigest() != row["artifact_sha256"]:
        raise ArtifactMismatch(
            f"{row['model_version_id']}: artifact {p} does not match its registered SHA-256"
        )
    return data


def load_models(conn: Conn, direction_model_version_id: str, move_model_version_id: str) -> LoadedModels:
    def mv(mid: str) -> dict[str, Any]:
        r = conn.execute("select * from model_versions where model_version_id = %s", (mid,)).fetchone()
        if r is None:
            raise KeyError(mid)
        return dict(r)

    d = mv(direction_model_version_id)
    if d["model_family"] != "market_logit":
        raise ValueError(f"{direction_model_version_id} is {d['model_family']}, not market_logit")
    art = json.loads(_artifact(d))
    base = conn.execute(
        "select model_version_id from model_versions where training_run_id = %s and model_family = 'class_frequency'",
        (d["training_run_id"],),
    ).fetchone()
    m = mv(move_model_version_id)
    if m["model_family"] != "gbdt":
        raise ValueError(f"{move_model_version_id} is {m['model_family']}, not gbdt")
    q = pickle.loads(_artifact(m))["model"]
    h = conn.execute(
        "select * from model_versions where training_run_id = %s and model_family = 'har_vol'",
        (m["training_run_id"],),
    ).fetchone()
    if base is None or h is None:
        raise KeyError("training run is missing its class_frequency or har_vol companion model")
    har = HarVol.from_dict(json.loads(_artifact(dict(h))))
    return LoadedModels(
        MarketLogit.from_dict(art),
        d["model_version_id"],
        d["status"],
        d["calibration_version"],
        base["model_version_id"],
        art["references"]["class_frequency"],
        q,
        m["model_version_id"],
        m["status"],
        har,
        h["model_version_id"],
    )


# ---------------------------------------------------------------- sampling (D-23, D-43)
@dataclass(frozen=True)
class Sampling:
    rule: str
    is_primary: bool
    slot_id: str | None = None
    schedule_version: str | None = None
    scheduled_for: datetime | None = None
    supersedes: str | None = None


def sampling_for(conn: Conn, snap: dict[str, Any], target_id: str, target_row_id: str) -> Sampling:
    primary = set(load("forecast")["primary_rules"])
    tt, as_of = snap["trigger_type"], snap["analysis_as_of"]
    if tt in ("scheduled", "session_check"):
        for s in schedule_slots(snap["session_date"]):
            if s.status == "scheduled" and s.scheduled_for == as_of and target_id in s.target_ids:
                return Sampling("schedule_slot", True, s.slot_id, s.schedule_version, s.scheduled_for)
        return Sampling("scheduled_5m", False)
    if tt == "event":
        prev = conn.execute(
            """select prediction_id from predictions where event_id = %s and target_row_id = %s and security_id = %s
                order by published_at desc nulls last limit 1""",
            (snap["trigger_ref"], target_row_id, snap["security_id"]),
        ).fetchone()
        if prev is None:
            return Sampling("event_first", "event_first" in primary)
        return Sampling("revision", False, supersedes=prev["prediction_id"])
    rule = {
        "market_move": "market_move_first",
        "on_demand": "on_demand",
        "user_supplement": "user_supplement",
    }[tt]
    return Sampling(rule, rule in primary)


def abstain_reason(
    snap: dict[str, Any], target_id: str, published_at: datetime, sampling: Sampling
) -> str | None:
    if snap["market_state"] == "halted":
        return "halted"
    if snap["market_state"] != "regular":
        return "market_closed"
    if sampling.rule == "schedule_slot" and sampling.scheduled_for is not None:
        if published_at > sampling.scheduled_for + timedelta(
            seconds=int(load("forecast")["publish_deadline_s"])
        ):
            return "slot_missed"
    if snap["data_quality"] == "stale":
        return "stale_quote"
    ready = (snap["prediction_readiness"] or {}).get("stock_reaction", {})
    if ready.get("status") != "ready" or snap["day_relative_pp"] is None:
        return "benchmark_unavailable"
    av = is_target_available(target_id, published_at)
    if not av.available:
        return av.abstain_reason or "window_insufficient"
    return None


# ---------------------------------------------------------------- run
@dataclass(frozen=True)
class ForecastResult:
    published: Published
    runs: list[dict[str, Any]]
    predictions: list[dict[str, Any]]
    features: pd.DataFrame = field(default_factory=pd.DataFrame)


def tier(model_status: str) -> str:
    """Only a live (approved) model is shown as validated; everything else stays internal (D-33)."""
    return "validated_public" if model_status == "live" else "internal_shadow"


def _target_row(target_id: str) -> str:
    return str(next(t for t in load("targets")["targets"] if t["target_id"] == target_id)["target_row_id"])


def _locked(
    snap: dict[str, Any], model_id: str, cal_version: str | None, sigma: dict[str, Any]
) -> dict[str, Any]:
    return {
        "target_definition_version": load("targets")["target_definition_version"],
        "quote_rule_version": load("quote_rules")["quote_rule_version"],
        "benchmark_version_id": snap["benchmark_version_id"],
        "calendar_version": get_calendar().session(snap["session_date"]).calendar_version,
        "model_version_id": model_id,
        "calibration_version": cal_version,
        "schema_version": sr.SCHEMA_VERSION,
        "sigma_model_version": sigma.get("sigma_model_version"),
        "sigma_hat_pp": sigma.get("sigma_hat_pp"),
        "threshold_k": sigma.get("threshold_k"),
        "threshold_pp": sigma.get("threshold_pp"),
        "feature_set_version": load("features/fs-0.2")["feature_set_version"],
    }


def forecast_snapshot(
    conn: Conn,
    snapshot_id: str,
    provider: Any,
    models: LoadedModels,
    history: pd.DataFrame,
    published_at: datetime,
    feature_dir: Path | None = None,
) -> ForecastResult:
    """`history`: realised windows (dataset-shaped rows) — only those ended by published_at are used."""
    snap = conn.execute(
        "select * from security_state_snapshots where snapshot_id = %s", (snapshot_id,)
    ).fetchone()
    if snap is None:
        raise KeyError(snapshot_id)
    snap = dict(snap)
    pub = ensure_utc(published_at, "published_at").to_pydatetime()
    if pub < snap["analysis_as_of"]:
        raise ValueError("published_at is before the snapshot's analysis_as_of")
    sec = snap["security_id"]
    _, weights = benchmark_version(conn, sec, snap["session_date"])
    constituents = list(weights)
    hist = realised_before(history[history["security_id"] == sec], pub)

    sig = estimate_sigma(
        hist.rename(columns={"t0_ts": "window_start", "end_ts": "window_end"})[
            ["window_start", "window_end", "relative_return_pp"]
        ],
        pub,
        pub,
    )
    lock = lock_threshold(sig.sigma_hat_pp)
    sigma: dict[str, Any] = (
        {
            "sigma_model_version": lock.sigma_model_version,
            "sigma_hat_pp": lock.sigma_hat_pp,
            "threshold_k": lock.threshold_k,
            "threshold_pp": lock.threshold_pp,
        }
        if not isinstance(lock, Abstain)
        else {
            "sigma_model_version": sig.sigma_model_version,
            "sigma_hat_pp": None,
            "threshold_k": None,
            "threshold_pp": None,
        }
    )
    series = series_for(provider, [sec, *constituents, *reference_ids()], pub)
    row = feature_row(series, sec, constituents, pub, snap["session_date"], sigma["sigma_hat_pp"], hist)

    run_tag = new_id("run")
    fdir = feature_dir or repo_root() / load("forecast")["feature_snapshot_dir"]
    fdir.mkdir(parents=True, exist_ok=True)
    fpath = fdir / f"{run_tag}.parquet"
    row.assign(published_at=pd.Timestamp(pub)).to_parquet(fpath, index=False)
    try:
        fs_id = str(fpath.relative_to(repo_root()))
    except ValueError:
        fs_id = str(fpath)

    deadline = snap["analysis_as_of"] + timedelta(seconds=int(load("forecast")["publish_deadline_s"]))
    valid_until = pub + timedelta(
        minutes=60, seconds=int(load("targets")["availability"]["regular_60m_settle_tolerance_s"])
    )
    event_id = snap["trigger_ref"] if snap["trigger_type"] == "event" else None
    runs, preds = [], []
    for target_id in load("forecast")["targets"]:
        trow = _target_row(target_id)
        sm = sampling_for(conn, snap, target_id, trow)
        reason = abstain_reason(snap, target_id, pub, sm)
        direction = target_id == "regular_60m"
        model_id = models.direction_id if direction else models.move_id
        baseline_id = models.baseline_id if direction else models.har_id
        cal_version = models.calibration_version if direction else "conformal"
        run_id = new_id("run")
        runs.append(
            {
                "run_id": run_id,
                "trigger_type": snap["trigger_type"],
                "trigger_ref": snap["trigger_ref"],
                "snapshot_id": snapshot_id,
                "event_analysis_ids": list(snap["event_analysis_ids"] or []),
                "feature_snapshot_id": fs_id,
                "model_version_id": model_id,
                "calibration_version": cal_version,
                "baseline_model_version_id": baseline_id,
                "evidence_gaps": [
                    i["issue"] for i in (snap["quality_issues"] or []) if isinstance(i, dict) and "issue" in i
                ],
                "publish_deadline": deadline,
                "published_at": pub,
                "idempotency_key": f"{sec}|{snapshot_id}|{target_id}|{model_id}",
            }
        )
        p: dict[str, Any] = {
            "prediction_id": new_id("pred"),
            "run_id": run_id,
            "target_row_id": trow,
            "security_id": sec,
            "event_id": event_id,
            "display_tier": tier(models.direction_status if direction else models.move_status),
            "is_primary": sm.is_primary,
            "sampling_rule": sm.rule,
            "schedule_slot_id": sm.slot_id,
            "schedule_version": sm.schedule_version,
            "scheduled_for": sm.scheduled_for,
            "supersedes_prediction_id": sm.supersedes,
            "valid_until": valid_until,
            "published_at": pub,
            "locked": _locked(snap, model_id, cal_version, sigma if direction else {}),
            "probabilities": None,
            "predicted_class": None,
            "sigma_hat_pp": sigma["sigma_hat_pp"] if direction else None,
            "threshold_pp": sigma["threshold_pp"] if direction else None,
            "move_quantiles": None,
            "edge_vs_baseline": None,
            "abstain_reason": None,
            "status": "published",
        }
        if reason is None and direction and isinstance(lock, Abstain):
            reason = lock.abstain_reason  # sigma unavailable -> insufficient_data (D-09)
        if reason is not None:
            p |= {"status": "abstained", "abstain_reason": reason}
        elif direction:
            probs = models.direction.proba(design(row, models.direction.features))[0]
            base = np.asarray([models.class_frequency[c] for c in CLASSES])
            p |= {
                "probabilities": {c: round(float(v), 6) for c, v in zip(CLASSES, probs, strict=True)},
                "predicted_class": CLASSES[int(np.argmax(probs))],
                "edge_vs_baseline": round(float(((probs - base) ** 2).sum()), 6),
            }
            s = sum(p["probabilities"].values())  # rounding must not break the DB sum check
            p["probabilities"][p["predicted_class"]] = round(
                p["probabilities"][p["predicted_class"]] + 1.0 - s, 6
            )
        else:
            q = models.move.predict(row)
            p["move_quantiles"] = {k: round(float(v[0]), 6) for k, v in q.items()} | {
                "unit": "abs_relative_pp"
            }
        preds.append(p)
    return ForecastResult(publish(conn, runs, preds), runs, preds, row)
