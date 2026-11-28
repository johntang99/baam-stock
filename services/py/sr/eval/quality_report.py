"""Data-quality report: abstentions, unsettleable outcomes and snapshot quality by reason (DP 2.06; AC-18; OQ-62).

Read-only. For each security over a session-date range:
- predictions: counts by status, abstentions by `abstain_reason`, unsettleable outcomes by the reporting
  settlement's `invalid_reason`, split by target and by sampling rule (primary schedule-slot samples first);
- snapshots: counts by `data_quality`, `run_state`, trigger type and quality-issue code.
Everything counted is visible at `as_of` (published / settled no later than it).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any

from sr.db import Conn
from sr.eval.fva import TARGET_OF
from sr.timeguard import ensure_utc


def quality_report(
    conn: Conn, start: date, end: date, as_of: datetime, security_ids: list[str] | None = None
) -> dict[str, Any]:
    t = ensure_utc(as_of, "as_of").to_pydatetime()
    preds = conn.execute(
        """select p.security_id, p.target_row_id, p.status, p.abstain_reason, p.sampling_rule, p.is_primary,
                  s.invalid_reason, s.outcome_class
             from predictions p join prediction_runs r using (run_id)
             join security_state_snapshots sn on sn.snapshot_id = r.snapshot_id
             left join prediction_settlements s on s.prediction_id = p.prediction_id and s.is_reporting_version
                  and s.settled_at <= %s
            where sn.session_date between %s and %s and p.published_at <= %s
              and (%s::text[] is null or p.security_id = any(%s::text[]))""",
        (t, start, end, t, security_ids, security_ids),
    ).fetchall()
    snaps = conn.execute(
        """select security_id, data_quality, run_state, trigger_type, quality_issues from security_state_snapshots
            where session_date between %s and %s and published_at <= %s
              and (%s::text[] is null or security_id = any(%s::text[]))""",
        (start, end, t, security_ids, security_ids),
    ).fetchall()

    by_sec: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "predictions": {
                "n": 0,
                "by_status": Counter(),
                "abstain_reasons": Counter(),
                "unsettleable_reasons": Counter(),
                "by_target": defaultdict(Counter),
                "primary": {"n": 0, "abstain_reasons": Counter()},
            },
            "snapshots": {
                "n": 0,
                "data_quality": Counter(),
                "run_state": Counter(),
                "trigger_type": Counter(),
                "issues": Counter(),
            },
        }
    )
    for p in preds:
        d = by_sec[p["security_id"]]["predictions"]
        d["n"] += 1
        d["by_status"][p["status"]] += 1
        tgt = TARGET_OF.get(p["target_row_id"], p["target_row_id"])
        d["by_target"][tgt][p["status"]] += 1
        if p["abstain_reason"]:
            d["abstain_reasons"][p["abstain_reason"]] += 1
        if p["invalid_reason"]:
            d["unsettleable_reasons"][p["invalid_reason"]] += 1
        if p["is_primary"]:
            d["primary"]["n"] += 1
            if p["abstain_reason"]:
                d["primary"]["abstain_reasons"][p["abstain_reason"]] += 1
    for s in snaps:
        d = by_sec[s["security_id"]]["snapshots"]
        d["n"] += 1
        d["data_quality"][s["data_quality"]] += 1
        d["run_state"][s["run_state"]] += 1
        d["trigger_type"][s["trigger_type"]] += 1
        for i in s["quality_issues"] or []:
            d["issues"][str(i.get("issue", "unknown"))] += 1

    def plain(x: Any) -> Any:
        if isinstance(x, dict):  # Counter and defaultdict are dicts
            return {k: plain(v) for k, v in sorted(x.items())}
        return x

    return {
        "report_version": "quality-report-0.1",
        "from": start.isoformat(),
        "to": end.isoformat(),
        "as_of": t.isoformat(),
        "securities": {k: plain(v) for k, v in sorted(by_sec.items())},
    }


def to_markdown(rep: dict[str, Any]) -> str:
    lines = [
        f"# 数据质量报表 {rep['from']} – {rep['to']}",
        "",
        f"截至 {rep['as_of']}（UTC）。只读统计；原因计数来自预测的 abstain_reason 与结算的 invalid_reason。",
        "",
        "| 证券 | 预测数 | 弃预测原因 | 无法结算原因 | 快照数 | 快照质量 | 问题 |",
        "|---|---|---|---|---|---|---|",
    ]

    def fmt(c: dict[str, int]) -> str:
        return "、".join(f"{k} {v}" for k, v in c.items()) or "—"

    for sec, d in rep["securities"].items():
        p, s = d["predictions"], d["snapshots"]
        lines.append(
            f"| {sec} | {p['n']} | {fmt(p['abstain_reasons'])} | {fmt(p['unsettleable_reasons'])} | {s['n']} | "
            f"{fmt(s['data_quality'])} | {fmt(s['issues'])} |"
        )
    return "\n".join(lines) + "\n"
