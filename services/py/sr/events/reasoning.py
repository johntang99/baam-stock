"""Step 2 reasoning trace (D-46; DC reasoning_trace; AC-10, AC-57).

Deterministic steps are produced by code: market_fact (relative return = stock − basket), timing_check (is the
evidence earlier than the move?), evidence_fact, gap, conclusion. Attribution / counter-evidence statements may be
drafted by an LLM but must cite (validated by sr.events.citations). A driver whose evidence all arrived after the
move started — or whose timing cannot be established — is never kept as a cause; it is listed as concurrent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sr.config import load
from sr.events.citations import Resolver, validate_explanation


@dataclass(frozen=True)
class MarketMove:
    move_start_at: datetime  # first quote of the move (from 1.09 market reaction)
    ref_before_quote_id: str
    ref_asof_quote_id: str
    stock_return_pct: float
    benchmark_return_pct: float | None  # None -> benchmark unavailable


@dataclass(frozen=True)
class EvidenceInfo:
    evidence_id: str
    claim: str
    source_published_at: datetime | None
    source_published_precision: str | None
    available_at: datetime
    verification_status: str
    item_ids: tuple[str, ...] = ()


def timing(ev: EvidenceInfo, move_start: datetime) -> tuple[str, str]:
    """('earlier' | 'later' | 'imprecise', note). Uses the earliest public time known precisely enough."""
    cfg = load("reasoning")["timing"]
    if ev.source_published_at is not None and ev.source_published_precision not in cfg["coarse_precisions"]:
        t = ev.source_published_at
    elif ev.source_published_at is None:
        t = ev.available_at  # only our own availability is known (an upper bound for public time)
        if t < move_start:
            return "earlier", cfg["earlier_note"]
        return "imprecise", cfg["imprecise_note"]
    else:
        return "imprecise", cfg["imprecise_note"]
    return ("earlier", cfg["earlier_note"]) if t < move_start else ("later", cfg["later_than_move_note"])


def build(
    move: MarketMove | None,
    evidence: list[EvidenceInfo],
    drafted_drivers: list[dict[str, Any]],
    drafted_counter: list[dict[str, Any]],
    resolver: Resolver,
    gaps: list[str] | None = None,
    analogue: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (market_explanation, reasoning_trace, rejected_statements)."""
    cfg = load("reasoning")
    trace: list[dict[str, Any]] = []
    expl: dict[str, Any] = {
        "status": "insufficient",
        "observed_facts": [],
        "possible_drivers": [],
        "counter_evidence": [],
        "unexplained": [],
        "concurrent_events": [],
    }

    def step(
        kind: str,
        conclusion: str,
        rule: str | None = None,
        confidence: str | None = None,
        **inputs: list[str],
    ) -> int:
        n = len(trace) + 1
        trace.append(
            {
                "step": n,
                "kind": kind,
                "inputs": {k: v for k, v in inputs.items()},
                "rule": rule,
                "conclusion": conclusion,
                "confidence": confidence,
            }
        )
        return n

    rel = None
    if move is None:
        step("gap", "无行情数据，无法计算个股与篮子的相对收益", rule="market_data_pending")
    else:
        q = [move.ref_before_quote_id, move.ref_asof_quote_id]
        if move.benchmark_return_pct is None:
            n = step(
                "market_fact",
                f"个股 {move.stock_return_pct:+.2f}%；篮子不可计算，相对收益为空",
                rule="相对收益 = 个股 − 篮子",
                confidence="high",
                quote_ids=q,
            )
            expl["observed_facts"].append(
                {
                    "text": f"个股 {move.stock_return_pct:+.2f}%（基准不可计算）",
                    "evidence_ids": [],
                    "quote_ids": q,
                    "item_ids": [],
                    "trace_step": n,
                }
            )
        else:
            rel = move.stock_return_pct - move.benchmark_return_pct
            n = step(
                "market_fact",
                f"个股 {move.stock_return_pct:+.2f}%，篮子 {move.benchmark_return_pct:+.2f}%，相对 {rel:+.2f}pp",
                rule="相对收益 = 个股 − 篮子",
                confidence="high",
                quote_ids=q,
            )
            expl["observed_facts"].append(
                {
                    "text": f"绝对 {move.stock_return_pct:+.2f}%，相对篮子 {rel:+.2f}pp",
                    "evidence_ids": [],
                    "quote_ids": q,
                    "item_ids": [],
                    "trace_step": n,
                }
            )

    valid_for_cause: set[str] = set()
    for ev in evidence:
        n = step(
            "evidence_fact",
            f"{ev.claim}（{ev.verification_status}）",
            evidence_ids=[ev.evidence_id],
            item_ids=list(ev.item_ids),
        )
        if ev.verification_status == "primary_confirmed":
            expl["observed_facts"].append(
                {
                    "text": ev.claim,
                    "evidence_ids": [ev.evidence_id],
                    "quote_ids": [],
                    "item_ids": list(ev.item_ids),
                    "trace_step": n,
                }
            )
        if move is not None:
            verdict, note = timing(ev, move.move_start_at)
            step(
                "timing_check",
                note,
                rule="证据公开时间早于异动开始",
                confidence="high" if verdict != "imprecise" else "low",
                evidence_ids=[ev.evidence_id],
            )
            if verdict == "earlier":
                valid_for_cause.add(ev.evidence_id)

    # LLM-drafted statements are citation-checked first; only valid ones may become causes or counter-evidence
    pre = validate_explanation(
        {
            "observed_facts": [],
            "possible_drivers": drafted_drivers,
            "counter_evidence": drafted_counter,
            "unexplained": [],
        },
        resolver,
    )
    early_rejected = pre.rejected
    expl["unexplained"].extend(pre.explanation["unexplained"])
    drafted_drivers, drafted_counter = (
        pre.explanation["possible_drivers"],
        pre.explanation["counter_evidence"],
    )

    for d in drafted_drivers:
        ids = set(d.get("evidence_ids", []))
        if move is not None and ids and not ids & valid_for_cause:
            n = step(
                "attribution",
                f"不采纳为原因：{d.get('text', '')}（{cfg['timing']['later_than_move_note']}或时间无法判定）",
                evidence_ids=sorted(ids),
            )
            expl["concurrent_events"].append({**d, "trace_step": n})
            continue
        n = step(
            "attribution",
            str(d.get("text", "")),
            evidence_ids=sorted(ids),
            quote_ids=list(d.get("quote_ids", [])),
        )
        expl["possible_drivers"].append({**d, "trace_step": n})
    for c in drafted_counter:
        n = step(
            "counter_check",
            str(c.get("text", "")),
            evidence_ids=list(c.get("evidence_ids", [])),
            quote_ids=list(c.get("quote_ids", [])),
        )
        expl["counter_evidence"].append({**c, "trace_step": n})
    if analogue:
        step("analogue", f"历史类比 n={analogue.get('n')}（只作参考）", rule=analogue.get("query_version"))
    for g in gaps or []:
        step("gap", g)

    rep = validate_explanation(expl, resolver)
    expl = rep.explanation
    rep.rejected[:0] = early_rejected
    for r in rep.rejected:
        step("gap", f"陈述被拒绝（{r['reason']}）：{r['text']}")
    residual = rel is not None and abs(rel) > float(cfg["status_rules"]["residual_unexplained_pp"])
    if residual and not expl["possible_drivers"]:
        expl["unexplained"].append(
            {
                "text": f"相对 {rel:+.2f}pp 未找到早于异动的已证实原因",
                "evidence_ids": [],
                "quote_ids": [],
                "item_ids": [],
                "trace_step": None,
            }
        )
    if expl["possible_drivers"] and not expl["unexplained"]:
        expl["status"] = "supported"
    elif expl["possible_drivers"] or expl["observed_facts"]:
        expl["status"] = "partial"
    step("conclusion", f"解释状态：{expl['status']}", confidence="medium")
    return expl, trace, rep.rejected
