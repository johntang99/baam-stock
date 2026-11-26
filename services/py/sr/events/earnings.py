"""Earnings documents -> verified facts -> event + evidence -> expectation comparison -> flash analysis (DP 1.07).

The flash analysis carries facts and the expectation comparison; the market reaction and explanation are added
by DP 1.09 once market data exists, so the hand-off says `missing_inputs / market_data_pending`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sr.config import load
from sr.db import Conn
from sr.events.expectations import compare
from sr.events.factcheck import CheckReport, check_facts
from sr.events.identity import earnings_key
from sr.events.merge import EvidenceIn, Link, attach_evidence
from sr.events.readiness import not_applicable, stock_reaction
from sr.events.versions import PublishResult, publish_analysis
from sr.evidence.collection_log import link_items
from sr.evidence.replay import PointInTimeReader, document_text
from sr.evidence.storage import LocalDocStorage
from sr.llm.base import LLMProvider, Mode

PRIMARY_KINDS = {"filing", "company_ir", "policy", "court", "insider_filing"}


@dataclass(frozen=True)
class EarningsOutcome:
    event_id: str | None
    facts: list[dict[str, Any]]
    expectation_comparison: dict[str, Any] | None
    missing_reason: str | None
    data_gaps: list[str]
    analysis_status: str
    published: list[PublishResult]
    check: CheckReport
    llm_call_id: str


def process_earnings_document(
    conn: Conn,
    doc_version_id: str,
    company_id: str,
    security_id: str,
    fiscal_period: str,
    provider: LLMProvider,
    expectation_snapshots: list[dict[str, Any]],
    analysis_as_of: datetime,
    published_at: datetime,
    storage: LocalDocStorage | None = None,
    mode: Mode = "live",
) -> EarningsOutcome:
    cfg = load("earnings")
    reader = PointInTimeReader(conn, analysis_as_of)
    row, text = document_text(reader, doc_version_id, storage or LocalDocStorage())
    src = conn.execute(
        """select ds.kind from source_document_versions v join source_documents d using (doc_id)
           join data_sources ds on ds.source_id = d.source_id where v.doc_version_id = %s""",
        (doc_version_id,),
    ).fetchone()
    disclosure_at = row["source_published_at"]
    gaps: list[str] = []
    if disclosure_at is None or row["source_published_precision"] in ("day", "unknown"):
        gaps.append("disclosure_time_imprecise")

    ext = provider.extract_facts(text, doc_version_id, mode=mode)
    if ext.status != "succeeded":
        rep = CheckReport()
        gaps.append(f"extraction_{ext.status}")
    else:
        rep = check_facts(ext.facts, fiscal_period, text)
        gaps += rep.gaps
    if not rep.accepted:
        return EarningsOutcome(
            None, [], None, "no_verified_facts", gaps, "needs_review", [], rep, ext.call_id
        )

    key = earnings_key(company_id, fiscal_period)
    verification = "primary_confirmed" if src and src["kind"] in PRIMARY_KINDS else "media_report"
    facts: list[dict[str, Any]] = []
    event_id = ""
    evidence_ids: list[str] = []
    for f in rep.accepted:
        m = attach_evidence(
            conn,
            key,
            cfg["event_category"],
            EvidenceIn(
                doc_version_id,
                f.quote,
                {**f.span, "llm_call_id": ext.call_id},
                verification,
                f"doc:{row['doc_id']}",
            ),
            [Link(security_id, "subject")],
            now=published_at,
        )
        event_id = m.event_id
        evidence_ids.append(m.evidence_id)
        entry: dict[str, Any] = {
            "metric": f.metric,
            "value": f.value,
            "unit": f.unit,
            "currency": f.currency,
            "period": f.period,
            "basis": f.basis,
            "direction": f.direction,
            "certainty": f.certainty,
            "evidence_ids": [m.evidence_id],
        }
        if disclosure_at is not None:
            cmp_, why = compare(f, company_id, expectation_snapshots, disclosure_at, analysis_as_of)
            entry["expectation_comparison"] = cmp_
            if why:
                entry["expectation_missing_reason"] = why
        facts.append(entry)

    link_items(conn, doc_version_id, event_id, evidence_ids)  # step-1 items -> event (D-45)
    headline = next((x for name in cfg["headline_metrics"] for x in facts if x["metric"] == name), facts[0])
    comparison = headline.get("expectation_comparison")
    missing = None if comparison else headline.get("expectation_missing_reason", "no_pre_event_consensus")
    status = "needs_review" if rep.rejected else "partial"
    observed = [
        {
            "text": f"{x['metric']} = {x['value']} {x['unit']} ({x['period']})",
            "evidence_ids": x["evidence_ids"],
            "quote_ids": [],
            "item_ids": [],
            "trace_step": 1,
        }
        for x in facts
    ]
    payload: dict[str, Any] = {
        "analysis_kind": "flash",
        "evidence_ids": evidence_ids,
        "facts": facts,
        "expectation_comparison": comparison,
        "missing_reason": missing,
        "data_gaps": [*gaps, "market_reaction_pending"],
        "market_reaction": {"missing_reason": "market_data_pending"},
        "market_explanation": {
            "status": "insufficient",
            "observed_facts": observed,
            "possible_drivers": [],
            "counter_evidence": [],
            "unexplained": ["市场反应待行情数据（D-13 / DP 1.09）"],
            "concurrent_events": [],
        },
        "prediction_readiness": {
            "event_outcome": not_applicable("no_open_outcome_question"),
            "stock_reaction": stock_reaction(cfg["event_category"], market_inputs_ready=False),
        },
        "rule_version": cfg["version"],
        "model_versions": {
            "llm_provider": provider.provider,
            "llm_model": provider.model,
            "llm_call_id": ext.call_id,
            "llm_prompt_version": getattr(provider, "version", "unknown"),
        },
    }
    if status == "needs_review":
        conn.execute(
            "update events set analysis_status = 'needs_review', row_version = row_version + 1 where event_id = %s",
            (event_id,),
        )
    pub = publish_analysis(conn, event_id, security_id, analysis_as_of, lambda s: payload, published_at)
    return EarningsOutcome(
        event_id, facts, comparison, missing, payload["data_gaps"], status, [pub], rep, ext.call_id
    )
