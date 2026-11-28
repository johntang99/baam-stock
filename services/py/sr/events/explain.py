"""Current explanation for an event analysis (DP 1.09; DC market_explanation / reasoning_trace; AC-10, AC-57).

Once quotes are available, the latest analysis for (event, security) is re-published as a new version (append-only,
supersedes the previous one) with:
- market_reaction from sr.events.reaction (ref quotes are written to reference_quotes so citations resolve);
- market_explanation + reasoning_trace from sr.events.reasoning: deterministic market and timing steps, evidence
  facts, LLM-drafted drivers only if they cite and their evidence came before the move start;
- data_gaps / prediction_readiness updated (market inputs ready only when the relative return is computable).

Evidence is read point-in-time: only event_evidence with available_at <= analysis_as_of.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from sr.config import load
from sr.db import Conn
from sr.events.citations import PgResolver, Resolver
from sr.events.exposure import impact_for
from sr.events.reaction import Reaction, compute_reaction, persist_quotes, window
from sr.events.readiness import not_applicable, stock_reaction
from sr.events.reasoning import EvidenceInfo, build
from sr.events.versions import (
    ARRAY_FIELDS,
    JSONB_FIELDS,
    TEXT_FIELDS,
    PublishResult,
    Snapshot,
    publish_analysis,
)
from sr.marketdata.quote_rules import evaluate_quotes
from sr.timeguard import ensure_utc

PENDING_GAP = "market_reaction_pending"


@dataclass(frozen=True)
class ExplainOutcome:
    publish: PublishResult
    reaction: Reaction
    market_explanation: dict[str, Any]
    reasoning_trace: list[dict[str, Any]]
    rejected: list[dict[str, Any]] = field(default_factory=list)


def basket_for(security_id: str, name: str = "semis_peer_v1") -> list[str]:
    """Peer basket security ids, target excluded (D-08)."""
    tickers = load("benchmarks")[name]["constituents"]
    return [f"sec_{t.lower()}" for t in tickers if f"sec_{t.lower()}" != security_id]


def evidence_for(conn: Conn, event_id: str, analysis_as_of: datetime) -> list[EvidenceInfo]:
    as_of = ensure_utc(analysis_as_of, "analysis_as_of").to_pydatetime()
    rows = conn.execute(
        """select e.evidence_id, e.claim, e.verification_status, e.available_at, e.doc_version_id,
                  v.source_published_at, v.source_published_precision
             from event_evidence e join source_document_versions v using (doc_version_id)
            where e.event_id = %s and e.available_at <= %s
            order by e.available_at, e.evidence_id""",
        (event_id, as_of),
    ).fetchall()
    out = []
    for r in rows:
        items = conn.execute(
            "select item_id from collection_items where doc_version_id = %s order by item_id",
            (r["doc_version_id"],),
        ).fetchall()
        out.append(
            EvidenceInfo(
                r["evidence_id"],
                r["claim"],
                r["source_published_at"],
                r["source_published_precision"],
                r["available_at"],
                r["verification_status"],
                tuple(i["item_id"] for i in items),
            )
        )
    return out


def anchor_at(evidence: list[EvidenceInfo]) -> datetime:
    """Earliest public time of the evidence: a precise source time, else our availability (OQ-43)."""
    coarse = set(load("reasoning")["timing"]["coarse_precisions"])
    times = [
        e.source_published_at
        if e.source_published_at is not None and e.source_published_precision not in coarse
        else e.available_at
        for e in evidence
    ]
    if not times:
        raise ValueError("no evidence visible at analysis_as_of")
    return min(times)


def quotes_for(
    provider: Any, security_id: str, basket: list[str], analysis_as_of: datetime, anchor: datetime
) -> pd.DataFrame:
    """Evaluated 1-second quotes for the reaction window (+ warm-up for the trailing median spread)."""
    start, end = window(analysis_as_of, anchor)
    warm = pd.Timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
    raw = provider.quotes_1s([security_id, *basket], (pd.Timestamp(start) - warm).to_pydatetime(), end)
    q = evaluate_quotes(raw)
    q = q[q["received_at"] <= ensure_utc(analysis_as_of, "as_of")]  # only what had arrived by then
    return q[q["ts"] >= pd.Timestamp(start)].reset_index(drop=True)


def _latest_payload(conn: Conn, snap: Snapshot) -> dict[str, Any]:
    if snap.latest_analysis_id is None:
        return {}
    row = conn.execute(
        "select * from event_analysis_versions where analysis_id = %s", (snap.latest_analysis_id,)
    ).fetchone()
    assert row is not None
    keep = (*JSONB_FIELDS, *TEXT_FIELDS, *ARRAY_FIELDS)
    return {k: copy.deepcopy(row[k]) for k in keep if row.get(k) is not None}


def _merge_prior_facts(
    expl: dict[str, Any], prior: dict[str, Any] | None, trace: list[dict[str, Any]]
) -> None:
    """Keep the previous version's cited observed facts (e.g. extracted earnings metrics), re-pointed at this
    trace's evidence_fact step for the same evidence."""
    if not prior:
        return
    step_for = {
        eid: s["step"]
        for s in trace
        if s["kind"] == "evidence_fact"
        for eid in s["inputs"].get("evidence_ids", [])
    }
    have = {f["text"] for f in expl["observed_facts"]}
    for f in prior.get("observed_facts", []):
        if not isinstance(f, dict) or f.get("text") in have:
            continue
        eids = [e for e in f.get("evidence_ids", []) if e in step_for]
        if not eids:
            continue  # its evidence is no longer visible / cited: do not carry it over
        expl["observed_facts"].append({**f, "evidence_ids": eids, "trace_step": step_for[eids[0]]})
        have.add(f["text"])


def publish_explanation(
    conn: Conn,
    event_id: str,
    security_id: str,
    analysis_as_of: datetime,
    published_at: datetime,
    quotes: pd.DataFrame,
    drafted_drivers: list[dict[str, Any]] | None = None,
    drafted_counter: list[dict[str, Any]] | None = None,
    resolver: Resolver | None = None,
    weights: dict[str, float] | None = None,
    vendor_source_id: str | None = None,
    valuation: dict[str, Any] | None = None,
) -> ExplainOutcome:
    """`quotes`: evaluated 1-second quotes visible at analysis_as_of (see quotes_for)."""
    evidence = evidence_for(conn, event_id, analysis_as_of)
    basket = list(weights) if weights else basket_for(security_id)
    reaction = compute_reaction(
        quotes, security_id, basket, anchor_at(evidence), analysis_as_of, weights, vendor_source_id
    )
    persist_quotes(conn, reaction.quote_rows)
    category_row = conn.execute(
        "select category, evidence_status from events where event_id = %s", (event_id,)
    ).fetchone()
    if category_row is None:
        raise KeyError(event_id)
    category = str(category_row["category"])
    confirmed = category_row["evidence_status"] == "primary_confirmed"
    gaps = (
        ["benchmark_unavailable"]
        if reaction.market_reaction["missing_reason"] == "benchmark_unavailable"
        else []
    )
    expl, trace, rejected = build(
        reaction.move,
        evidence,
        list(drafted_drivers or []),
        list(drafted_counter or []),
        resolver or PgResolver(conn),
        gaps=gaps or None,
    )
    ready = reaction.market_reaction["relative_return_pp"] is not None
    unconfirmed = [] if confirmed else [e for e in evidence if e.verification_status == "media_report"]
    for (
        e
    ) in unconfirmed:  # AC-41: a media report is labelled until primary evidence confirms the event (OQ-55)
        expl["unexplained"].append(
            {
                "text": f"未经证实：{e.claim}（媒体报道，待公司公告或官方来源确认）",
                "evidence_ids": [e.evidence_id],
                "quote_ids": [],
                "item_ids": list(e.item_ids),
                "trace_step": None,
            }
        )
    if unconfirmed:
        gaps.append("unconfirmed_evidence")

    def compute(snap: Snapshot) -> dict[str, Any]:
        payload = _latest_payload(conn, snap)
        new_expl = copy.deepcopy(expl)
        _merge_prior_facts(new_expl, payload.get("market_explanation"), trace)
        if new_expl["status"] == "insufficient" and new_expl["observed_facts"]:
            new_expl["status"] = "partial"  # same rule as reasoning.build, after carried-over facts
        if valuation is not None:  # background only (DP 1.24, AC-42); absent without a licensed source
            new_expl["valuation_context"] = valuation
        elif "valuation_context" in (payload.get("market_explanation") or {}):
            new_expl["valuation_context"] = payload["market_explanation"]["valuation_context"]
        stale = {PENDING_GAP} | ({"unconfirmed_evidence"} if not unconfirmed else set())
        data_gaps = [g for g in payload.get("data_gaps", []) if g not in stale]
        data_gaps += [g for g in gaps if g not in data_gaps]
        readiness = dict(payload.get("prediction_readiness") or {})
        readiness.setdefault("event_outcome", not_applicable("no_open_outcome_question"))
        readiness["stock_reaction"] = stock_reaction(category, market_inputs_ready=ready)
        mv = dict(payload.get("model_versions") or {})
        mv |= {"reaction": reaction.detail["version"], "reasoning": load("reasoning")["version"]}
        return {
            "analysis_kind": "flash",  # the first analysis of an event built here is a flash (DC analysis_kind)
            **payload,
            "evidence_ids": sorted({*payload.get("evidence_ids", []), *(e.evidence_id for e in evidence)}),
            "impact": payload.get("impact")
            or impact_for(
                conn, event_id, security_id, [e.claim for e in evidence], [e.evidence_id for e in evidence]
            ),  # per-security record from its own link relation (DP 2.05)
            "market_reaction": reaction.market_reaction,
            "market_explanation": new_expl,
            "reasoning_trace": trace,
            "data_gaps": data_gaps,
            "prediction_readiness": readiness,
            "model_versions": mv,
        }

    pub = publish_analysis(conn, event_id, security_id, analysis_as_of, compute, published_at)
    return ExplainOutcome(pub, reaction, expl, trace, rejected)
