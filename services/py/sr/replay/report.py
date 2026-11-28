"""Line-by-line verification report (DP 1.17; DP Phase 1 acceptance: "任取一条预测能列出锁定输入、起算/结算报价、
收益、类别与结算理由"; OQ-51).

prediction_report() gathers everything one forecast depended on from the database — the snapshot it was built on
(watermarks, market state, day return, event analyses, quality), the locked versions, the model and its feature row,
the t0 and end quotes, the reporting settlement (returns, class / move, Brier / pinball, reason) — and runs the
automatic checks: published before t0, inputs read no later than publication, end quote at or after the target
time, every locked key present, exactly one reporting settlement. Rendered as Markdown and (escaped) HTML.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from sr.config import repo_root
from sr.db import Conn

LOCKED_KEYS = (
    "target_definition_version",
    "quote_rule_version",
    "benchmark_version_id",
    "calendar_version",
    "model_version_id",
    "calibration_version",
    "schema_version",
    "sigma_model_version",
    "sigma_hat_pp",
    "threshold_k",
    "threshold_pp",
    "feature_set_version",
)


def _quote(conn: Conn, qid: str | None) -> dict[str, Any] | None:
    if not qid:
        return None
    r = conn.execute(
        "select quote_id, security_id, quote_ts, received_at, bid, ask, mid, is_qualifying from reference_quotes where quote_id = %s",
        (qid,),
    ).fetchone()
    return dict(r) if r else None


def _features(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    p = p if p.is_absolute() else repo_root() / p
    if not p.exists():
        return {"_missing": str(p)}
    row = pd.read_parquet(p).iloc[0].to_dict()
    return {str(k): (None if isinstance(v, float) and v != v else v) for k, v in row.items()}


def prediction_report(conn: Conn, prediction_id: str) -> dict[str, Any]:
    p = conn.execute("select * from predictions where prediction_id = %s", (prediction_id,)).fetchone()
    if p is None:
        raise KeyError(prediction_id)
    p = dict(p)
    run = dict(
        conn.execute("select * from prediction_runs where run_id = %s", (p["run_id"],)).fetchone() or {}
    )
    snap = dict(
        conn.execute(
            "select * from security_state_snapshots where snapshot_id = %s", (run.get("snapshot_id"),)
        ).fetchone()
        or {}
    )
    model = dict(
        conn.execute(
            "select model_version_id, model_family, status, training_run_id, artifact_sha256 from model_versions where model_version_id = %s",
            (run.get("model_version_id"),),
        ).fetchone()
        or {}
    )
    settles = [
        dict(s)
        for s in conn.execute(
            "select * from prediction_settlements where prediction_id = %s order by settlement_version",
            (prediction_id,),
        ).fetchall()
    ]
    rep = next((s for s in settles if s["is_reporting_version"]), None)
    t0 = _quote(conn, p["t0_quote_id"])
    end = _quote(conn, rep["end_quote_id"]) if rep else None
    feats = _features(run.get("feature_snapshot_id"))

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool | None, note: str = "") -> None:
        checks.append(
            {"check": name, "result": "n/a" if ok is None else ("pass" if ok else "FAIL"), "note": note}
        )

    check("locked keys present (DC §3.7)", all(k in (p["locked"] or {}) for k in LOCKED_KEYS))
    check(
        "published_at < t0 quote_ts (AC-13)",
        None if t0 is None else p["published_at"] < t0["quote_ts"],
        "" if t0 else "no t0 (abstained, or no sync quote)",
    )
    check(
        "inputs read no later than publication",
        None if not snap else snap["analysis_as_of"] <= p["published_at"],
        f"snapshot as_of {snap.get('analysis_as_of')}",
    )
    check(
        "watermarks not after the snapshot as_of",
        None
        if not snap
        else (
            snap["evidence_watermark"] <= snap["analysis_as_of"]
            and snap["market_watermark"] <= snap["analysis_as_of"]
        ),
    )
    check(
        "end quote at/after target_end_at (D-07)",
        None if not (end and p["target_end_at"]) else end["quote_ts"] >= p["target_end_at"],
    )
    check(
        "exactly one reporting settlement",
        None if not settles else sum(s["is_reporting_version"] for s in settles) == 1,
        f"{len(settles)} version(s)",
    )
    if rep and p["probabilities"] and rep["outcome_class"]:
        check(
            "hit = predicted class == outcome", rep["hit"] == (p["predicted_class"] == rep["outcome_class"])
        )
    return {
        "prediction": p,
        "run": run,
        "snapshot": snap,
        "model": model,
        "features": feats,
        "t0_quote": t0,
        "end_quote": end,
        "settlement": rep,
        "settlement_versions": len(settles),
        "checks": checks,
    }


# ---------------------------------------------------------------- rendering
def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def to_markdown(r: dict[str, Any]) -> str:
    p, s, snap, st = r["prediction"], r["settlement"], r["snapshot"], r["run"]
    lines = [
        f"## {p['prediction_id']} · {p['target_row_id']} · {p['security_id']}",
        "",
        f"- 状态 status: **{p['status']}**" + (f"（{p['abstain_reason']}）" if p["abstain_reason"] else ""),
        f"- 抽样 sampling: {p['sampling_rule']}"
        + (f" / slot {p['schedule_slot_id']}" if p["schedule_slot_id"] else "")
        + f" · primary={p['is_primary']} · tier={p['display_tier']}",
        f"- 发布 published_at: {_fmt(p['published_at'])} · valid_until {_fmt(p['valid_until'])}",
    ]
    if p["probabilities"]:
        lines.append(
            "- 概率 probabilities: "
            + ", ".join(f"{k} {v:.3f}" for k, v in p["probabilities"].items())
            + f" → **{p['predicted_class']}** · 阈值 ±{_fmt(p['threshold_pp'])}pp（σ̂ {_fmt(p['sigma_hat_pp'])}）"
        )
    if p["move_quantiles"]:
        lines.append(
            "- 预期波动 move: "
            + ", ".join(f"{k} {v}" for k, v in p["move_quantiles"].items() if k != "unit")
            + " pp"
        )
    lines += [
        "",
        "**快照 snapshot**",
        "",
        f"- {snap.get('snapshot_id')} · as_of {_fmt(snap.get('analysis_as_of'))} · {snap.get('market_state')} · 质量 {snap.get('data_quality')}",
        f"- 水位 evidence {_fmt(snap.get('evidence_watermark'))} · market {_fmt(snap.get('market_watermark'))}",
        f"- 当日 day {_fmt(snap.get('day_return_pct'))}% · 相对 {_fmt(snap.get('day_relative_pp'))}pp · 事件分析 {snap.get('event_analysis_ids') or []}",
        f"- 解释 {snap.get('explanation_status')}：{snap.get('explanation_summary')}",
        "",
        "**锁定输入 locked**",
        "",
        "| 字段 | 值 |",
        "|---|---|",
    ]
    lines += [f"| {k} | {_fmt((p['locked'] or {}).get(k))} |" for k in LOCKED_KEYS]
    lines += [
        "",
        f"模型 model: {r['model'].get('model_version_id')} ({r['model'].get('model_family')}, {r['model'].get('status')}) · 特征 {st.get('feature_snapshot_id')}",
    ]
    feats = {k: v for k, v in r["features"].items() if k.startswith("f_") or k.startswith("har_")}
    if feats:
        lines.append(
            "特征 features: "
            + ", ".join(f"{k.removeprefix('f_')}={_fmt(v)}" for k, v in sorted(feats.items())[:24])
        )
    lines += ["", "**起算 / 结算报价 quotes**", "", "| | quote_id | quote_ts | mid |", "|---|---|---|---|"]
    for name, q in (("t0", r["t0_quote"]), ("end", r["end_quote"])):
        lines.append(
            f"| {name} | {_fmt(q and q['quote_id'])} | {_fmt(q and q['quote_ts'])} | {_fmt(q and float(q['mid']))} |"
        )
    lines += ["", "**结算 settlement**", ""]
    if s:
        lines += [
            f"- 版本 v{s['settlement_version']}（共 {r['settlement_versions']} 版）· settled_at {_fmt(s['settled_at'])}",
            f"- 收益 stock {_fmt(s['stock_return_pct'] and float(s['stock_return_pct']))}% · basket {_fmt(s['benchmark_return_pct'] and float(s['benchmark_return_pct']))}% · 相对 {_fmt(s['relative_return_pp'] and float(s['relative_return_pp']))}pp",
            f"- 类别 outcome: {_fmt(s['outcome_class'])} · hit {_fmt(s['hit'])} · Brier {_fmt(s['brier'] and float(s['brier']))}"
            + (
                f" · |move| {_fmt(float(s['abs_relative_move_pp']))} · pinball {s['pinball_loss']} · hits {s['quantile_hits']}"
                if s["abs_relative_move_pp"] is not None
                else ""
            ),
            f"- 理由 reason: {s['reason_text']}",
        ]
    else:
        lines.append(
            "- 未结算（" + ("弃预测，不结算" if p["status"] == "abstained" else "未到期或待起算") + "）"
        )
    lines += ["", "**核验 checks**", "", "| 检查 | 结果 | 说明 |", "|---|---|---|"]
    lines += [f"| {c['check']} | {c['result']} | {c['note']} |" for c in r["checks"]]
    return "\n".join(lines) + "\n"


def to_html(md_sections: list[str], title: str) -> str:
    """A self-contained page: each Markdown section shown pre-formatted (escaped; no script, no external assets)."""
    body = "\n".join(f"<section><pre>{html.escape(m)}</pre></section>" for m in md_sections)
    return (
        f'<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
        "<style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
        "pre{white-space:pre-wrap;background:#f6f6f6;padding:1rem;border-radius:6px}</style></head>"
        f"<body><h1>{html.escape(title)}</h1><p>SYNTHETIC / 虚构 data unless the market-data source says otherwise.</p>{body}</body></html>\n"
    )


def write_json_reports(reports: list[dict[str, Any]], out_dir: Path, synthetic: bool = True) -> list[Path]:
    """One JSON file per prediction for the read-only web page (DP 1.19): <out_dir>/<prediction_id>.json."""
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for r in reports:
        p = out_dir / f"{r['prediction']['prediction_id']}.json"
        p.write_text(
            json.dumps({"synthetic": synthetic, **r}, ensure_ascii=False, indent=2, default=str) + "\n"
        )
        paths.append(p)
    return paths


def day_report(conn: Conn, security_id: str, session_date: date) -> tuple[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """select p.prediction_id from predictions p join prediction_runs r using (run_id)
             join security_state_snapshots s on s.snapshot_id = r.snapshot_id
            where p.security_id = %s and s.session_date = %s order by p.published_at, p.target_row_id""",
        (security_id, session_date),
    ).fetchall()
    reps = [prediction_report(conn, r["prediction_id"]) for r in rows]
    head = [
        f"# 回放报告 replay report · {security_id} · {session_date}",
        "",
        "| 预测 | 目标 | 发布 | 状态 | 类别/幅度 | 命中 | 检查 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in reps:
        p, s = r["prediction"], r["settlement"]
        res = (
            "—"
            if not s
            else (
                s["outcome_class"]
                or (
                    f"{float(s['abs_relative_move_pp']):.3f}pp"
                    if s["abs_relative_move_pp"] is not None
                    else s["invalid_reason"]
                )
            )
        )
        fails = sum(c["result"] == "FAIL" for c in r["checks"])
        head.append(
            f"| {p['prediction_id']} | {p['target_row_id']} | {_fmt(p['published_at'])} | {p['status']} | {res} | {_fmt(s and s['hit'])} | {'✅' if not fails else f'❌ {fails}'} |"
        )
    return "\n".join(head) + "\n\n" + "\n".join(to_markdown(r) for r in reps), reps
