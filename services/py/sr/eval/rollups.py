"""Forecast accuracy rollups (DP 1.26; DC forecast_accuracy_rollups; D-23, D-44; AC-53; OQ-57).

refresh_rollups() recomputes, for each security x target, groups `all` and `slot:<slot_id>` of PRIMARY forecasts
(D-23: the schedule-slot samples are the main score) over the windows `session`, `rolling_20d`, `rolling_60d` and
`since_live` (since the first forecast of the newest model version used). Counts are always written; the metrics
stay null when fewer than `min_settled_for_metrics` forecasts settled ("样本不足": counts only). Read-only towards
predictions and settlements.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np

from sr.calendar import get_calendar
from sr.config import load
from sr.db import Conn, jsonb
from sr.eval.fva import TARGET_OF
from sr.eval.metrics import CLASSES, brier, brier_skill_score
from sr.timeguard import ensure_utc


def _rows(conn: Conn, as_of: datetime) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """select p.prediction_id, p.security_id, p.target_row_id, p.status, p.schedule_slot_id, p.probabilities, p.predicted_class,
                      p.published_at, r.model_version_id, r.baseline_model_version_id, sn.session_date,
                      s.outcome_class, s.hit, s.brier, s.invalid_reason, s.relative_return_pp,
                      f.inside_p80, f.inside_p90, f.residual_pp, f.abs_move_error_pp, p.interval, p.move_quantiles
                 from predictions p join prediction_runs r using (run_id)
                 join security_state_snapshots sn on sn.snapshot_id = r.snapshot_id
                 left join prediction_settlements s on s.prediction_id = p.prediction_id and s.is_reporting_version and s.settled_at <= %s
                 left join forecast_vs_actual f on f.prediction_id = p.prediction_id
                where p.is_primary and p.published_at <= %s""",
            (as_of, as_of),
        ).fetchall()
    ]


def _width(r: dict[str, Any]) -> float | None:
    if r["interval"]:
        q = r["interval"]["quantiles"]
        return float(q["p90"]) - float(q["p10"])
    if r["move_quantiles"]:
        return float(r["move_quantiles"]["p80"])  # one-sided [0, p80] for the absolute move
    return None


def metrics(rows: list[dict[str, Any]], class_freq: dict[str, float] | None) -> dict[str, Any]:
    cfg = load("eval_fva")
    settled = [r for r in rows if r["status"] == "settled" and r["invalid_reason"] is None]
    out: dict[str, Any] = {
        "n_published": len(rows),
        "n_settled": len(settled),
        "n_abstained": sum(r["status"] == "abstained" for r in rows),
        "n_unsettleable": sum(r["status"] == "unsettleable" for r in rows),
        "hit_rate": None,
        "brier": None,
        "bss_class_frequency": None,
        "coverage_p80": None,
        "coverage_p90": None,
        "mean_interval_width_pp": None,
        "mean_residual_pp": None,
        "mean_abs_residual_pp": None,
        "calibration_bins": [],
    }
    if len(settled) < int(cfg["min_settled_for_metrics"]):
        return out  # 样本不足: counts only
    direction = [r for r in settled if r["probabilities"] and r["outcome_class"]]
    if direction:
        out["hit_rate"] = float(np.mean([bool(r["hit"]) for r in direction]))
        b = float(np.mean([float(r["brier"]) for r in direction]))
        out["brier"] = b
        if class_freq:
            ref = float(np.mean([brier(class_freq, r["outcome_class"]) for r in direction]))
            out["bss_class_frequency"] = brier_skill_score(b, ref)
        width = float(cfg["calibration_bin_width"])
        bins: dict[int, list[bool]] = defaultdict(list)
        for r in direction:
            top = max(r["probabilities"].values())
            b = min(
                math.floor(top / width + 1e-9), round(1 / width) - 1
            )  # 0.6 / 0.1 is 5.999… in floating point
            bins[b].append(r["predicted_class"] == r["outcome_class"])
        out["calibration_bins"] = [
            {
                "p_low": round(k * width, 6),
                "p_high": round((k + 1) * width, 6),
                "n": len(v),
                "observed": float(np.mean(v)),
            }
            for k, v in sorted(bins.items())
        ]
    for key, col in (("coverage_p80", "inside_p80"), ("coverage_p90", "inside_p90")):
        vals = [bool(r[col]) for r in settled if r[col] is not None]
        out[key] = float(np.mean(vals)) if vals else None
    widths = [w for w in (_width(r) for r in settled) if w is not None]
    out["mean_interval_width_pp"] = float(np.mean(widths)) if widths else None
    res = [
        float(r["residual_pp"] if r["residual_pp"] is not None else r["abs_move_error_pp"])
        for r in settled
        if r["residual_pp"] is not None or r["abs_move_error_pp"] is not None
    ]
    if res:
        out["mean_residual_pp"], out["mean_abs_residual_pp"] = (
            float(np.mean(res)),
            float(np.mean(np.abs(res))),
        )
    return out


def refresh_rollups(conn: Conn, as_of: datetime) -> int:
    cfg = load("eval_fva")
    t = ensure_utc(as_of, "as_of").to_pydatetime()
    cal = get_calendar()
    today = cal.session_for_instant(t).session_date
    rows = _rows(conn, t)
    freq_of: dict[str, dict[str, float]] = {}
    for r in conn.execute(
        "select model_version_id, hyperparams from model_versions where model_family = 'class_frequency'"
    ).fetchall():
        hp = r["hyperparams"] or {}
        if "class_frequency" in hp:
            freq_of[r["model_version_id"]] = {c: float(hp["class_frequency"][c]) for c in CLASSES}
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_key[(r["security_id"], TARGET_OF[r["target_row_id"]])].append(r)
    n = 0
    for (sec, target), group in by_key.items():
        sessions = sorted({r["session_date"] for r in group})
        newest_model = max(group, key=lambda r: r["published_at"])["model_version_id"]
        since_live = min(r["published_at"] for r in group if r["model_version_id"] == newest_model)
        last = {k: [s for s in sessions if s <= today][-int(v) :] for k, v in cfg["windows"].items()}
        windows = {
            "session": [r for r in group if r["session_date"] == today],
            "rolling_20d": [r for r in group if r["session_date"] in set(last["rolling_20d"])],
            "rolling_60d": [r for r in group if r["session_date"] in set(last["rolling_60d"])],
            "since_live": [r for r in group if r["published_at"] >= since_live],
        }
        for win, wrows in windows.items():
            gkeys: dict[str, list[dict[str, Any]]] = {"all": wrows}
            for r in wrows:
                if r["schedule_slot_id"]:
                    gkeys.setdefault(f"slot:{r['schedule_slot_id']}", []).append(r)
            for gk, grows in gkeys.items():
                base = grows[0]["baseline_model_version_id"] if grows else None
                m = metrics(grows, freq_of.get(base or ""))
                row = {
                    "security_id": sec,
                    "target_id": target,
                    "group_key": gk,
                    "window": win,
                    **m,
                    "model_version_ids": sorted({r["model_version_id"] for r in grows}),
                    "computed_at": t,
                }
                cols = list(row)
                with conn.transaction():
                    conn.execute(
                        'delete from forecast_accuracy_rollups where security_id = %s and target_id = %s and group_key = %s and "window" = %s',
                        (sec, target, gk, win),
                    )
                    conn.execute(
                        f"""insert into forecast_accuracy_rollups ({", ".join('"window"' if c == "window" else c for c in cols)})
                            values ({", ".join("%s::target_id" if c == "target_id" else "%s::rollup_window" if c == "window" else "%s" for c in cols)})""",
                        [jsonb(row[c]) if c == "calibration_bins" else row[c] for c in cols],
                    )
                n += 1
    return n
