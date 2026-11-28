"""Settlement for regular_60m and regular_60m_move (DP 1.15; AC-14, AC-15, AC-27; D-05..D-07; DC §3.7, §4; OQ-49).

settle(): start = the prediction's attached t0 quotes (attached here if missing), end = the first sync qualifying
quote at or after target_end_at within the settle tolerance; only quotes received by the settlement run time count.
Direction -> outcome class by the LOCKED threshold, hit, Brier; move -> |relative|, pinball per quantile, quantile
hits. Halt / missing quotes / basket -> unsettleable with the DC invalid_reason.

Append-only: an identical result returns the reporting version unchanged (idempotent); a different result (e.g. a
delayed quote has since arrived) appends version n+1 and moves the reporting flag to it — no row is ever rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import pandas as pd

from sr.benchmark.basket import basket_return
from sr.config import load
from sr.db import Conn, jsonb
from sr.eval.metrics import brier, pinball_by_quantile, quantile_hits
from sr.events.reaction import persist_quotes, quote_id, quote_row
from sr.forecast.publish import attach_t0
from sr.ids import new_id
from sr.labels.thresholds import classify
from sr.marketdata.corporate_actions import actions_crossing, adjust_start
from sr.marketdata.sync import find_first_sync_qualifying
from sr.timeguard import assert_not_after, ensure_utc

COMPARE = (
    "start_quote_id",
    "end_quote_id",
    "stock_return_pct",
    "benchmark_return_pct",
    "relative_return_pp",
    "outcome_class",
    "invalid_reason",
    "abs_relative_move_pp",
)


@dataclass(frozen=True)
class SettleResult:
    status: Literal["settled", "unsettleable", "unchanged", "not_due", "not_settleable"]
    settlement_id: str | None = None
    settlement_version: int | None = None
    row: dict[str, Any] | None = None
    detail: str = ""


def weights_for(conn: Conn, benchmark_version_id: str) -> dict[str, float]:
    r = conn.execute(
        "select constituents from benchmark_versions where benchmark_version_id = %s", (benchmark_version_id,)
    ).fetchone()
    if r is None:
        raise KeyError(benchmark_version_id)
    return {c["security_id"]: float(c["weight"]) for c in r["constituents"]}


def _mids(conn: Conn, ids: list[str]) -> dict[str, float]:
    rows = conn.execute(
        "select quote_id, security_id, mid from reference_quotes where quote_id = any(%s)", (ids,)
    ).fetchall()
    return {r["security_id"]: float(r["mid"]) for r in rows}


def _reason_text(r: dict[str, Any], p: dict[str, Any]) -> str:
    if r["invalid_reason"]:
        why = {
            "no_sync_start_quote": "发布后 30 秒内没有个股与篮子同步的合格报价，无法起算",
            "no_sync_end_quote": "目标时点后 30 秒内没有同步合格报价，无法结算",
            "halted": "窗口内个股停牌或 LULD 暂停",
            "benchmark_unavailable": "篮子成分缺失超过 1 只，基准不可计算",
        }.get(r["invalid_reason"], r["invalid_reason"])
        return f"无法结算：{why}（{r['invalid_reason']}）。"
    rel = r["relative_return_pp"]
    if r["outcome_class"] is not None:
        thr = float(p["threshold_pp"])
        hit = "命中" if r["hit"] else "未命中"
        return f"相对篮子 {rel:+.3f}pp，阈值 ±{thr:.3f}pp → {r['outcome_class']}；预测 {p['predicted_class']}，{hit}。"
    hits = ", ".join(f"{k}{'内' if v else '外'}" for k, v in (r["quantile_hits"] or {}).items())
    return f"实际幅度 {r['abs_relative_move_pp']:.3f}pp；{hits}。"


def compute(
    conn: Conn, p: dict[str, Any], quotes: pd.DataFrame, as_of: datetime, vendor_source_id: str | None = None
) -> dict[str, Any] | None:
    """Settlement fields for a prediction with an attached t0, or None when the window is not over yet."""
    sync = load("quote_rules")["sync"]
    tol_s = int(sync["settle_tolerance_s"])
    w = weights_for(conn, p["locked"]["benchmark_version_id"])
    base: dict[str, Any] = {
        "start_quote_id": p["t0_quote_id"],
        "end_quote_id": None,
        "benchmark_start_quote_ids": list(p["t0_benchmark_quote_ids"] or []),
        "benchmark_end_quote_ids": [],
        "stock_return_pct": None,
        "benchmark_return_pct": None,
        "relative_return_pp": None,
        "outcome_class": None,
        "hit": None,
        "brier": None,
        "abs_relative_move_pp": None,
        "pinball_loss": None,
        "quantile_hits": None,
        "invalid_reason": None,
    }
    if p["t0_quote_id"] is None:
        return base | {"invalid_reason": "no_sync_start_quote"}
    end_at = ensure_utc(p["target_end_at"], "target_end_at")
    if end_at + timedelta(seconds=tol_s) > ensure_utc(as_of, "as_of"):
        return None  # not due: never peek at a window that has not closed
    e = find_first_sync_qualifying(
        end_at.to_pydatetime(),
        p["security_id"],
        list(w),
        int(sync["tolerance_ms"]),
        tol_s,
        quotes=quotes,
        inclusive=True,
        as_of=as_of,
        invalid_reason_if_none="no_sync_end_quote",
    )
    t0 = conn.execute(
        "select quote_ts from reference_quotes where quote_id = %s", (p["t0_quote_id"],)
    ).fetchone()
    assert t0 is not None
    if e.status == "ok" and e.sample_ts is not None:
        stock_rows = quotes[
            (quotes["security_id"] == p["security_id"])
            & (quotes["ts"] >= pd.Timestamp(t0["quote_ts"]).floor("1s"))
            & (quotes["ts"] <= e.sample_ts)
        ]
        if bool(stock_rows["halted"].any()) or bool(stock_rows["luld_pause"].any()):
            return base | {"invalid_reason": "halted"}
    if e.status != "ok" or e.sample_ts is None or e.quote is None:
        # a halt that runs past the end also leaves no end quote: report it as the halt
        s = quotes[
            (quotes["security_id"] == p["security_id"])
            & (quotes["ts"] >= pd.Timestamp(t0["quote_ts"]).floor("1s"))
            & (quotes["ts"] <= end_at + timedelta(seconds=tol_s))
        ]
        halted = bool(s["halted"].any()) or bool(s["luld_pause"].any())
        return base | {"invalid_reason": "halted" if halted else "no_sync_end_quote"}
    rule = load("quote_rules")["quote_rule_version"]
    vendor = vendor_source_id or str(load("reaction")["vendor_source_id"])
    persist_quotes(
        conn,
        [quote_row(e.quote, e.sample_ts, vendor, rule)]
        + [quote_row(c, e.sample_ts, vendor, rule) for c in e.constituent_quotes.values()],
    )
    start: dict[str, float | None] = dict(_mids(conn, [p["t0_quote_id"], *base["benchmark_start_quote_ids"]]))
    # D-40: a window that crosses a corporate action is settled on an adjusted start price (raw quotes untouched)
    crossing = actions_crossing(
        conn,
        [p["security_id"], *w],
        pd.Timestamp(t0["quote_ts"]).to_pydatetime(),
        e.sample_ts.to_pydatetime(),
        as_of,
    )
    applied: list[str] = []
    for sid in [p["security_id"], *w]:
        acts = [a for a in crossing if a["security_id"] == sid]
        if not acts or start.get(sid) is None:
            continue
        adj = adjust_start(float(start[sid]), acts, None)  # type: ignore[arg-type]
        if adj.invalid_reason:
            if sid == p["security_id"]:
                return base | {"invalid_reason": adj.invalid_reason}
            start[sid] = None  # a constituent with an unknown ratio counts as missing (D-06)
        else:
            start[sid] = adj.price
            applied += list(adj.applied)
    base["_corporate_actions"] = applied
    stock = (float(e.quote["mid"]) / float(start[p["security_id"]]) - 1.0) * 100.0  # type: ignore[arg-type]
    br = basket_return(
        {c: start.get(c) for c in w}, {c: e.constituent_quotes.get(c, {}).get("mid") for c in w}, w
    )
    end_ids = sorted(quote_id(c, e.sample_ts) for c in e.constituent_quotes)
    out = base | {
        "end_quote_id": quote_id(p["security_id"], e.sample_ts),
        "benchmark_end_quote_ids": end_ids,
        "stock_return_pct": round(stock, 9),
    }
    if br.status != "ok" or br.return_pct is None:
        return out | {"invalid_reason": "benchmark_unavailable"}
    rel = stock - br.return_pct
    out |= {"benchmark_return_pct": round(br.return_pct, 9), "relative_return_pp": round(rel, 9)}
    if p["probabilities"] is not None:
        outcome = classify(rel, float(p["threshold_pp"]))
        out |= {
            "outcome_class": outcome,
            "hit": p["predicted_class"] == outcome,
            "brier": round(brier(p["probabilities"], outcome), 9),
        }
    if p["move_quantiles"] is not None:
        q = {k: float(v) for k, v in p["move_quantiles"].items() if k != "unit"}
        y = abs(rel)
        out |= {
            "abs_relative_move_pp": round(y, 9),
            "pinball_loss": {k: round(v, 9) for k, v in pinball_by_quantile(q, y).items()},
            "quantile_hits": quantile_hits(q, y),
        }
    return out


def _same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    def norm(v: Any) -> Any:
        return (
            None
            if v is None
            else (round(float(v), 9) if isinstance(v, (int, float)) or hasattr(v, "as_tuple") else v)
        )

    return all(norm(a.get(k)) == norm(b.get(k)) for k in COMPARE)


def settle(
    conn: Conn,
    prediction_id: str,
    quotes: pd.DataFrame,
    as_of: datetime,
    settled_at: datetime | None = None,
    vendor_source_id: str | None = None,
) -> SettleResult:
    """`quotes`: evaluated 1-second quotes covering [published_at, target_end_at + 30 s], received by `as_of`."""
    assert_not_after(
        quotes["received_at"], as_of, "settlement quotes"
    )  # late quotes count only once received
    p = conn.execute("select * from predictions where prediction_id = %s", (prediction_id,)).fetchone()
    if p is None:
        raise KeyError(prediction_id)
    if p["status"] in ("abstained", "pending_evaluation", "not_triggered"):
        return SettleResult("not_settleable", detail=str(p["status"]))
    if p["t0_quote_id"] is None and p["status"] == "published":
        w = weights_for(conn, p["locked"]["benchmark_version_id"])
        if ensure_utc(p["published_at"], "published_at") + timedelta(
            seconds=int(load("quote_rules")["sync"]["start_max_wait_s"])
        ) > ensure_utc(as_of, "as_of"):
            return SettleResult("not_due", detail="t0 search window still open")
        attach_t0(conn, prediction_id, quotes, w, as_of, vendor_source_id)
        p = conn.execute("select * from predictions where prediction_id = %s", (prediction_id,)).fetchone()
        assert p is not None
    fields = compute(conn, dict(p), quotes, as_of, vendor_source_id)
    if fields is None:
        return SettleResult("not_due", detail="window not over")
    cur = conn.execute(
        "select * from prediction_settlements where prediction_id = %s and is_reporting_version",
        (prediction_id,),
    ).fetchone()
    if cur is not None and _same(dict(cur), {k: v for k, v in fields.items() if not k.startswith("_")}):
        return SettleResult("unchanged", cur["settlement_id"], cur["settlement_version"], dict(cur))
    last = conn.execute(
        "select coalesce(max(settlement_version), 0) as v from prediction_settlements where prediction_id = %s",
        (prediction_id,),
    ).fetchone()
    version = int(last["v"] if last else 0) + 1
    row = {
        "settlement_id": new_id("stl"),
        "prediction_id": prediction_id,
        "settlement_version": version,
        **fields,
        "settled_at": ensure_utc(settled_at or as_of, "settled_at").to_pydatetime(),
        "is_reporting_version": True,
    }
    applied = row.pop("_corporate_actions", None) or []
    row["reason_text"] = _reason_text(row, dict(p)) + (
        f" 起算价已按公司行为调整（{', '.join(applied)}）。" if applied else ""
    )
    status = "unsettleable" if row["invalid_reason"] else "settled"
    jcols = {"pinball_loss", "quantile_hits"}
    with conn.transaction():
        if cur is not None:
            conn.execute(
                "update prediction_settlements set is_reporting_version = false where settlement_id = %s",
                (cur["settlement_id"],),
            )
        cols = list(row)
        marks = ", ".join(f"%s{'::invalid_reason' if c == 'invalid_reason' else ''}" for c in cols)
        conn.execute(
            f"insert into prediction_settlements ({', '.join(cols)}) values ({marks})",
            [jsonb(row[c]) if c in jcols and row[c] is not None else row[c] for c in cols],
        )
        conn.execute(
            "update predictions set status = %s::prediction_status where prediction_id = %s",
            (status, prediction_id),
        )
    return SettleResult(status, row["settlement_id"], version, row)  # type: ignore[arg-type]


def quality_summary(conn: Conn, target_row_id: str) -> dict[str, Any]:
    """Hit rate over settled predictions only; unsettleable ones are counted by reason, outside the denominator (AC-15)."""
    rows = conn.execute(
        """select s.hit, s.invalid_reason from prediction_settlements s join predictions p using (prediction_id)
            where s.is_reporting_version and p.target_row_id = %s""",
        (target_row_id,),
    ).fetchall()
    settled = [r for r in rows if r["invalid_reason"] is None]
    hits = [r["hit"] for r in settled if r["hit"] is not None]
    by: dict[str, int] = {}
    for r in rows:
        if r["invalid_reason"]:
            by[r["invalid_reason"]] = by.get(r["invalid_reason"], 0) + 1
    return {
        "n_settled": len(settled),
        "hit_rate": (sum(hits) / len(hits)) if hits else None,
        "unsettleable": by,
    }
