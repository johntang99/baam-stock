"""Policy event template (DP 1.08): Federal Register document -> event (policy:<AGENCY>:<doc no>), official
evidence, milestones by document type, exposure links by topic, per-security flash analysis.

Exposure direction is left `unknown` (S2: impact needs company disclosure / analysis, not keyword guesses);
the stock-reaction hand-off allows only the market baseline until event-enhanced models are validated (AC-12).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sr.config import load
from sr.db import Conn
from sr.events.identity import policy_key
from sr.events.merge import EvidenceIn, Link, attach_evidence, set_progress_status
from sr.events.milestones import ensure_milestone
from sr.events.readiness import stock_reaction
from sr.events.versions import PublishResult, publish_analysis
from sr.evidence.replay import PointInTimeReader, document_text
from sr.evidence.sources.federal_register import date_et_midnight
from sr.evidence.storage import LocalDocStorage
from sr.timeguard import ensure_utc


@dataclass
class PolicyOutcome:
    event_id: str | None
    template: str | None
    topics: list[str]
    links: list[Link]
    milestones: list[dict[str, Any]] = field(default_factory=list)
    published: list[PublishResult] = field(default_factory=list)
    progress_status: str | None = None
    data_gaps: list[str] = field(default_factory=list)


def _template(rec: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    slugs = {a.get("slug") for a in rec.get("agencies", [])}
    for name, t in load("policy_templates")["templates"].items():
        if slugs & set(t["agency_slugs"]):
            return name, t
    return None


def match_topics(rec: dict[str, Any], tpl: dict[str, Any]) -> list[str]:
    text = " ".join(str(rec.get(k) or "") for k in ("title", "abstract", "action")).lower()
    return [
        name for name, topic in tpl["topics"].items() if any(k.lower() in text for k in topic["keywords"])
    ]


def process_policy_document(
    conn: Conn,
    doc_version_id: str,
    analysis_as_of: datetime,
    published_at: datetime,
    storage: LocalDocStorage | None = None,
) -> PolicyOutcome:
    reader = PointInTimeReader(conn, analysis_as_of)
    row, text = document_text(reader, doc_version_id, storage or LocalDocStorage())
    rec = json.loads(text)
    found = _template(rec)
    if found is None:
        return PolicyOutcome(None, None, [], [], data_gaps=["no_policy_template_for_agency"])
    tname, tpl = found
    topics = match_topics(rec, tpl)
    links: dict[str, Link] = {}
    for t in topics:
        topic = tpl["topics"][t]
        for lk in topic["links"]:
            prev = links.get(lk["security_id"])
            if prev is None or (prev.relation != "regulated_party" and lk["relation"] == "regulated_party"):
                links[lk["security_id"]] = Link(lk["security_id"], lk["relation"], topic["exposure_note"])
    gaps = [] if topics else ["no_exposure_topic_matched"]

    key = policy_key(tpl["identity_agency"], rec["document_number"])
    claim = f"{rec.get('type', '')}: {rec.get('title', '')}".strip(": ")
    m = attach_evidence(
        conn,
        key,
        tpl["category"],
        EvidenceIn(
            doc_version_id,
            claim,
            {"field": "title"},
            "primary_confirmed",
            f"fr:{rec['document_number']}",
            claimant=", ".join(a.get("name", "") for a in rec.get("agencies", [])),
        ),
        list(links.values()),
        now=published_at,
    )

    asof = ensure_utc(analysis_as_of, "analysis_as_of").to_pydatetime()
    milestones = []
    for spec in tpl["milestones"].get(rec.get("type", ""), []):
        raw = rec.get(spec["at"])
        if not raw:
            gaps.append(f"milestone_date_missing:{spec['type']}")
            continue
        at = date_et_midnight(raw)
        occurred = spec.get("status") == "occurred" or at <= asof
        mid, created = ensure_milestone(
            conn,
            m.event_id,
            spec["type"],
            at,
            occurred,
            decision_body=tpl["identity_agency"],
            evidence_ids=[m.evidence_id],
        )
        milestones.append(
            {"milestone_id": mid, "type": spec["type"], "at": at, "occurred": occurred, "created": created}
        )

    progress = None
    eff = rec.get("effective_on")
    if rec.get("type") == "Rule" and eff and date_et_midnight(eff) <= asof:
        set_progress_status(conn, m.event_id, "effective")
        progress = "effective"
    if rec.get("type") == "Rule" and not eff:
        gaps.append("effective_date_missing")

    published = []
    for lk in links.values():
        impact = [
            {
                "fact": claim,
                "exposure": lk.exposure_note,
                "channel": tpl["category"],
                "direction": "unknown",
                "horizon": "pending_company_disclosure",
                "evidence_ids": [m.evidence_id],
            }
        ]
        payload: dict[str, Any] = {
            "analysis_kind": "flash",
            "evidence_ids": [m.evidence_id],
            "impact": impact,
            "facts": [
                {
                    "metric": "rule_effective_date",
                    "value": None,
                    "unit": "date",
                    "currency": None,
                    "period": eff,
                    "basis": None,
                    "evidence_ids": [m.evidence_id],
                    **({} if eff else {"null_reason": "effective_date_missing"}),
                }
            ],
            "data_gaps": [*gaps, "market_reaction_pending", "company_disclosure_pending"],
            "market_reaction": {"missing_reason": "market_data_pending"},
            "market_explanation": {
                "status": "insufficient",
                "observed_facts": [
                    {
                        "text": f"{claim}（{rec.get('publication_date')} 公布，精度=日）",
                        "evidence_ids": [m.evidence_id],
                        "quote_ids": [],
                        "item_ids": [],
                        "trace_step": 1,
                    }
                ],
                "possible_drivers": [],
                "counter_evidence": [],
                "unexplained": ["对该证券的影响方向待公司披露与行情数据确认"],
                "concurrent_events": [],
            },
            "prediction_readiness": {
                "event_outcome": {"status": "manual_review", "reason": "outcome_question_not_defined"},
                "stock_reaction": stock_reaction(tpl["category"], market_inputs_ready=False),
            },
            "rule_version": load("policy_templates")["version"],
            "model_versions": {"template": tname, "topics": topics},
        }

        def _payload(_snap: object, p: dict[str, Any] = payload) -> dict[str, Any]:
            return p

        published.append(
            publish_analysis(conn, m.event_id, lk.security_id, analysis_as_of, _payload, published_at)
        )
    return PolicyOutcome(
        m.event_id, tname, topics, list(links.values()), milestones, published, progress, gaps
    )
