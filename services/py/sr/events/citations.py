"""Citation validation for market_explanation (D-46; AC-57).

Every statement in observed_facts / possible_drivers / counter_evidence must cite >= 1 evidence or quote, and every
cited id must exist (event_evidence, reference_quotes, collection_items; with a collection run given, cited
evidence must come from a document collected in that run). Failing statements are rejected and moved to
`unexplained` with a note — never silently kept.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Protocol

from sr.config import load
from sr.db import Conn


class Resolver(Protocol):
    def missing(self, kind: str, ids: list[str]) -> set[str]: ...


class PgResolver:
    _SQL = {
        "evidence": "select evidence_id as id from event_evidence where evidence_id = any(%s)",
        "quote": "select quote_id as id from reference_quotes where quote_id = any(%s)",
        "item": "select item_id as id from collection_items where item_id = any(%s)",
    }

    def __init__(self, conn: Conn, collection_run_id: str | None = None) -> None:
        self.conn, self.run = conn, collection_run_id

    def missing(self, kind: str, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        if kind == "evidence" and self.run:
            rows = self.conn.execute(
                """select e.evidence_id as id from event_evidence e join collection_items ci
                     on ci.doc_version_id = e.doc_version_id and ci.collection_run_id = %s
                   where e.evidence_id = any(%s)""",
                (self.run, ids),
            ).fetchall()
        elif kind == "item" and self.run:
            rows = self.conn.execute(
                "select item_id as id from collection_items where collection_run_id = %s and item_id = any(%s)",
                (self.run, ids),
            ).fetchall()
        else:
            rows = self.conn.execute(self._SQL[kind], (ids,)).fetchall()
        return set(ids) - {r["id"] for r in rows}


@dataclass
class CitationReport:
    explanation: dict[str, Any]
    rejected: list[dict[str, Any]] = field(default_factory=list)  # {section, text, reason}


def _as_statement(s: Any) -> dict[str, Any]:
    if isinstance(s, str):
        return {"text": s, "evidence_ids": [], "quote_ids": [], "item_ids": [], "trace_step": None}
    return {"evidence_ids": [], "quote_ids": [], "item_ids": [], "trace_step": None, **s}


def validate_explanation(explanation: dict[str, Any], resolver: Resolver) -> CitationReport:
    cfg = load("reasoning")
    out = copy.deepcopy(explanation)
    out.setdefault("unexplained", [])
    rep = CitationReport(out)
    for section in cfg["cited_sections"]:
        kept = []
        for raw in out.get(section, []):
            st = _as_statement(raw)
            reason = None
            if not st["evidence_ids"] and not st["quote_ids"]:
                reason = "no_citation"
            else:
                bad = (
                    resolver.missing("evidence", st["evidence_ids"])
                    | resolver.missing("quote", st["quote_ids"])
                    | resolver.missing("item", st["item_ids"])
                )
                if bad:
                    reason = "unknown_citation:" + ",".join(sorted(bad))
            if reason:
                rep.rejected.append({"section": section, "text": st["text"], "reason": reason})
                out["unexplained"].append(
                    {
                        **st,
                        "text": st["text"] + cfg["uncited_note"],
                        "evidence_ids": [],
                        "quote_ids": [],
                        "item_ids": [],
                    }
                )
            else:
                kept.append(st)
        out[section] = kept
    return rep
