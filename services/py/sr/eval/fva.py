"""Forecast vs actual (DP 1.26; DC forecast_vs_actual; D-44; AC-53; OQ-57).

refresh_fva() rebuilds one row per published forecast (abstentions have no forecast and no row):
- forecast_path: the LOCKED quantiles at the window end, intermediate points scaled by sqrt(t/T) ("sqrt_time_v1",
  display only — not a multi-horizon model); direction forecasts use their display interval (p10/p50/p90),
  expected-move forecasts their move quantiles (p50/p80/p90);
- actual_path: the relative return vs the basket at each minute after t0 from sync qualifying quotes received by
  `as_of` (never later); the end point of a settled forecast is the reporting settlement's own relative return;
- outcome / hit / Brier from the reporting settlement, inside_p80 / inside_p90, residual_pp, abs_move_error_pp.
Read-only towards predictions: only forecast_vs_actual rows are replaced.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sr.benchmark.basket import basket_return
from sr.config import load
from sr.db import Conn, jsonb
from sr.events.reaction import sync_points
from sr.marketdata.quote_rules import evaluate_quotes
from sr.settle.settle import weights_for
from sr.timeguard import ensure_utc

TARGET_OF = {
    "tgt_regular_60m_v1": "regular_60m",
    "tgt_regular_60m_move_v1": "regular_60m_move",
    "tgt_regular_to_close_v1": "regular_to_close",
    "tgt_next_regular_session_v1": "next_regular_session",
}


def forecast_path(p: dict[str, Any], minutes: int, step: int) -> dict[str, Any]:
    if p["move_quantiles"]:
        end = {k: float(v) for k, v in p["move_quantiles"].items() if k != "unit"}
        unit = "abs_relative_pp"
    elif p["interval"]:
        end = {k: float(v) for k, v in p["interval"]["quantiles"].items() if k in ("p10", "p50", "p90")}
        unit = "relative_pp"
    else:
        return {"method": "none", "unit": None, "points": []}
    pts = []
    for m in range(0, minutes + 1, step):
        f = math.sqrt(m / minutes) if minutes else 1.0
        pts.append({"min": m, **{k: round(v * f, 9) for k, v in end.items()}})
    if pts[-1]["min"] != minutes:
        pts.append({"min": minutes, **{k: round(v, 9) for k, v in end.items()}})
    return {"method": "sqrt_time_v1", "unit": unit, "points": pts}


def actual_path(
    conn: Conn,
    p: dict[str, Any],
    quotes: pd.DataFrame,
    as_of: datetime,
    minutes: int,
    settled_rel: float | None,
) -> list[dict[str, Any]]:
    if not p["t0_quote_id"]:
        return []
    w = weights_for(conn, p["locked"]["benchmark_version_id"])
    rows = conn.execute(
        "select security_id, mid, quote_ts from reference_quotes where quote_id = any(%s)",
        ([p["t0_quote_id"], *(p["t0_benchmark_quote_ids"] or [])],),
    ).fetchall()
    start = {r["security_id"]: float(r["mid"]) for r in rows}
    t0 = next(r["quote_ts"] for r in rows if r["security_id"] == p["security_id"])
    t0s = pd.Timestamp(t0).floor("1s")
    cutoff = ensure_utc(as_of, "as_of")
    tol = int(load("quote_rules")["sync"]["settle_tolerance_s"])
    out = [{"min": 0, "relative_pp": 0.0}]
    for m in range(1, minutes + 1):
        mark = t0s + pd.Timedelta(minutes=m)
        if mark > cutoff:
            break  # never show what had not arrived yet
        pts = sync_points(
            quotes, p["security_id"], list(w), mark, min(mark + pd.Timedelta(seconds=tol), cutoff)
        )
        if not pts:
            continue
        pt = pts[0]
        stock = (float(pt.stock["mid"]) / start[p["security_id"]] - 1.0) * 100.0
        br = basket_return(
            {c: start.get(c) for c in w}, {c: pt.constituents.get(c, {}).get("mid") for c in w}, w
        )
        if br.status == "ok" and br.return_pct is not None:
            out.append({"min": m, "relative_pp": round(stock - br.return_pct, 9)})
    if settled_rel is not None:  # the end point is the settlement itself
        out = [x for x in out if x["min"] < minutes] + [{"min": minutes, "relative_pp": float(settled_rel)}]
    return out


def _quotes(provider: Any, conn: Conn, p: dict[str, Any], as_of: datetime) -> pd.DataFrame:
    w = weights_for(conn, p["locked"]["benchmark_version_id"])
    warm = timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
    end = min(ensure_utc(p["target_end_at"], "end") + timedelta(seconds=60), ensure_utc(as_of, "as_of"))
    q = evaluate_quotes(
        provider.quotes_1s([p["security_id"], *w], p["published_at"] - warm, end.to_pydatetime())
    )
    return q[q["received_at"] <= pd.Timestamp(as_of)].reset_index(drop=True)


def refresh_fva(conn: Conn, provider: Any, as_of: datetime, prediction_ids: list[str] | None = None) -> int:
    cfg = load("eval_fva")
    preds = conn.execute(
        """select * from predictions where published_at <= %s and status not in ('abstained', 'pending_evaluation')
              and (%s::text[] is null or prediction_id = any(%s))""",
        (ensure_utc(as_of, "as_of").to_pydatetime(), prediction_ids, prediction_ids),
    ).fetchall()
    n = 0
    for p in preds:
        p = dict(p)
        minutes = (
            int(round((p["target_end_at"] - p["published_at"]).total_seconds() / 60))
            if p["target_end_at"]
            else 60
        )
        minutes = 60 if p["target_row_id"] in ("tgt_regular_60m_v1", "tgt_regular_60m_move_v1") else minutes
        s = conn.execute(
            "select * from prediction_settlements where prediction_id = %s and is_reporting_version and settled_at <= %s",
            (p["prediction_id"], ensure_utc(as_of, "as_of").to_pydatetime()),
        ).fetchone()
        rel = float(s["relative_return_pp"]) if s and s["relative_return_pp"] is not None else None
        fp = forecast_path(p, minutes, int(cfg["path_step_min"]))
        ap = (
            actual_path(conn, p, _quotes(provider, conn, p, as_of), as_of, minutes, rel)
            if p["target_end_at"]
            else []
        )
        end = fp["points"][-1] if fp["points"] else {}
        inside80 = inside90 = residual = move_err = None
        if rel is not None and p["interval"]:
            q = p["interval"]["quantiles"]
            inside80 = float(q["p10"]) <= rel <= float(q["p90"])
            inside90 = float(q["p05"]) <= rel <= float(q["p95"]) if "p05" in q else None
            residual = rel - float(q["p50"])
        if s and s["abs_relative_move_pp"] is not None and p["move_quantiles"]:
            y = float(s["abs_relative_move_pp"])
            inside80, inside90 = (
                y <= float(p["move_quantiles"]["p80"]),
                y <= float(p["move_quantiles"]["p90"]),
            )
            move_err = y - float(p["move_quantiles"]["p50"])
        session = conn.execute(
            "select s.session_date from prediction_runs r join security_state_snapshots s using (snapshot_id) where r.run_id = %s",
            (p["run_id"],),
        ).fetchone()
        t0 = (
            conn.execute(
                "select quote_ts from reference_quotes where quote_id = %s", (p["t0_quote_id"],)
            ).fetchone()
            if p["t0_quote_id"]
            else None
        )
        row = {
            "prediction_id": p["prediction_id"],
            "security_id": p["security_id"],
            "session_date": session["session_date"] if session else ensure_utc(p["published_at"], "p").date(),
            "target_id": TARGET_OF[p["target_row_id"]],
            "schedule_slot_id": p["schedule_slot_id"],
            "t0_at": t0["quote_ts"] if t0 else None,
            "target_end_at": p["target_end_at"],
            "forecast_path": fp,
            "actual_path": ap,
            "status": p["status"],
            "outcome_class": s["outcome_class"] if s else None,
            "hit": s["hit"] if s else None,
            "brier": float(s["brier"]) if s and s["brier"] is not None else None,
            "inside_p80": inside80,
            "inside_p90": inside90,
            "residual_pp": None if residual is None else round(residual, 9),
            "abs_move_error_pp": None if move_err is None else round(move_err, 9),
        }
        assert not end or end.get("min") == minutes
        cols = list(row)
        with conn.transaction():
            conn.execute("delete from forecast_vs_actual where prediction_id = %s", (p["prediction_id"],))
            conn.execute(
                f"insert into forecast_vs_actual ({', '.join(cols)}) values ({', '.join('%s::target_id' if c == 'target_id' else '%s::prediction_status' if c == 'status' else '%s' for c in cols)})",
                [jsonb(row[c]) if c in ("forecast_path", "actual_path") else row[c] for c in cols],
            )
        n += 1
    return n
