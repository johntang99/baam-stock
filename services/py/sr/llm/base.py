"""LLMProvider interface (MP §3.2) + shared validation and call logging.

Rules (MP §7-1, S3§6): the LLM never produces probabilities; every extracted fact carries a verbatim quote that
must be found in the source document (char span checked by code) — otherwise the whole call is rejected and
nothing from it reaches events or features. No tools / web search, in live or replay mode.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

from sr.config import load
from sr.db import Conn, jsonb
from sr.evidence.hashing import sha256_text
from sr.ids import new_id

Mode = Literal["live", "replay"]
CallStatus = Literal["succeeded", "rejected_validation", "refused", "failed"]


# JSON schema the model must return (structured output). Kept here so prompt_hash changes when it changes.
def _facts_schema() -> dict[str, Any]:
    """Output schema; metric and unit vocabularies come from config/earnings.yaml (prompt_hash changes with them)."""
    ecfg = load("earnings")
    nullable_str = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    return {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "enum": [*ecfg["metrics"], "other"]},
                        "metric_label": {"type": "string"},
                        "value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                        "unit": {"type": "string", "enum": list(ecfg["units"])},
                        "currency": nullable_str,
                        "period": nullable_str,
                        "segment": nullable_str,
                        "basis": {
                            "anyOf": [
                                {"type": "string", "enum": ["gaap", "non_gaap", "company_defined"]},
                                {"type": "null"},
                            ]
                        },
                        "quote": {"type": "string"},
                        "direction": {
                            "type": "string",
                            "enum": ["increase", "decrease", "unchanged", "none"],
                        },
                        "scope": {
                            "type": "string",
                            "enum": ["company", "segment", "product", "geography", "other"],
                        },
                        "certainty": {
                            "type": "string",
                            "enum": ["reported", "guidance", "expectation", "hypothetical"],
                        },
                    },
                    "required": [
                        "metric",
                        "metric_label",
                        "value",
                        "unit",
                        "currency",
                        "period",
                        "segment",
                        "basis",
                        "quote",
                        "direction",
                        "scope",
                        "certainty",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["facts"],
        "additionalProperties": False,
    }


FACTS_SCHEMA: dict[str, Any] = _facts_schema()


@dataclass(frozen=True)
class ExtractedFact:
    metric: str
    value: float | None
    unit: str
    currency: str | None
    period: str | None
    basis: str | None
    quote: str
    span: dict[str, int]  # {"char_start", "char_end"} into the document text (computed by code)
    direction: str | None = None  # increase | decrease | unchanged | none   (D-32 field group "direction")
    scope: str | None = None  # company | segment | product | geography | other
    certainty: str | None = None  # reported | guidance | expectation | hypothetical
    metric_label: str | None = None  # the document's own wording ("Data Center segment revenue")
    segment: str | None = None  # segment / product line the fact is about; None = whole company


@dataclass(frozen=True)
class ExtractionResult:
    status: CallStatus
    facts: tuple[ExtractedFact, ...]
    call_id: str
    rejected: tuple[str, ...] = ()  # why validation failed (quotes not found …)


@dataclass(frozen=True)
class ExplanationInputs:
    security_id: str
    statements: list[dict[str, Any]]  # pre-cited candidate statements {text, evidence_ids, quote_ids}
    context: str = ""


@dataclass(frozen=True)
class ExplanationDraft:
    status: CallStatus
    drivers: tuple[dict[str, Any], ...]
    counter_evidence: tuple[dict[str, Any], ...]
    call_id: str


@dataclass
class CallRecord:
    purpose: str
    provider: str
    model: str
    prompt_version: str
    prompt_hash: str
    input_hash: str
    mode: Mode
    request_params: dict[str, Any]
    status: CallStatus
    doc_version_id: str | None = None
    output_hash: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None
    error: dict[str, Any] | None = None
    latency_ms: int | None = None
    call_id: str = field(default_factory=lambda: new_id("llm"))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CallLogger(Protocol):
    def log(self, rec: CallRecord) -> None: ...


class ListCallLogger:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    def log(self, rec: CallRecord) -> None:
        self.records.append(rec)


class PgCallLogger:
    def __init__(self, conn: Conn) -> None:
        self.conn = conn

    def log(self, rec: CallRecord) -> None:
        d = asdict(rec)
        for k in ("request_params", "usage", "error"):
            d[k] = jsonb(d[k]) if d[k] is not None else None
        cols = list(d)
        self.conn.execute(
            f"insert into llm_calls ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
            [d[c] for c in cols],
        )


@runtime_checkable
class LLMProvider(Protocol):
    provider: str
    model: str

    def extract_facts(
        self, doc_text: str, doc_version_id: str | None = None, mode: Mode = "live"
    ) -> ExtractionResult: ...

    def draft_explanation(self, inputs: ExplanationInputs, mode: Mode = "live") -> ExplanationDraft: ...


# ---------------------------------------------------------------- shared helpers
EXTRACT_SYSTEM = (
    "You extract financial and business facts from one source document for a research database.\n"
    "Rules:\n"
    "- Use only the document between <document> tags. Do not use outside knowledge, memory, or assumptions.\n"
    "- `quote`: copy the exact characters from the document (findable by string search) - the sentence, clause or "
    'table row that states the fact, including its scale (e.g. "$13.4 billion" or a row header like "($M)").\n'
    "- `metric`: pick the closest name from the allowed list; use `other` if none fits. `metric_label` is the "
    "document's own wording. EPS must state `basis` (gaap / non_gaap) or be skipped.\n"
    '- `segment`: the segment or product line a figure belongs to (e.g. "Data Center"); null for company-wide '
    "figures. `scope` must agree (segment / product / geography / company).\n"
    '- `value` is the number as printed; `unit` gives its scale (USD_billion for "$13.4 billion", USD_million for '
    "a ($M) table, USD_per_share for EPS, pct for percentages). null value when the fact is not numeric.\n"
    '- `period` is the fiscal period the figure covers (e.g. "third quarter of fiscal 2026"); for tables with '
    "several period columns, extract only figures whose period is unambiguous.\n"
    "- `direction`: the change the document states for this fact (increase / decrease / unchanged), or none. "
    "`certainty`: reported (actual result), guidance (company outlook), expectation (someone else's estimate), or "
    "hypothetical.\n"
    "- If the document states no facts, return an empty list. Never estimate or fill gaps."
)


def prompt_hash(system: str, schema: dict[str, Any], version: str) -> str:
    return sha256_text(json.dumps({"v": version, "system": system, "schema": schema}, sort_keys=True))


def locate_facts(doc_text: str, raw_facts: list[dict[str, Any]]) -> tuple[list[ExtractedFact], list[str]]:
    """Find each quote verbatim in the document; compute char spans. Any miss => rejected reasons."""
    facts, missing = [], []
    for f in raw_facts:
        q = (f.get("quote") or "").strip()
        i = doc_text.find(q) if q else -1
        if i < 0:
            missing.append(f"quote not found in source: {q[:80]!r}")
            continue
        facts.append(
            ExtractedFact(
                metric=str(f["metric"]),
                value=f.get("value"),
                unit=str(f.get("unit") or ""),
                currency=f.get("currency"),
                period=f.get("period"),
                basis=f.get("basis"),
                quote=q,
                span={"char_start": i, "char_end": i + len(q)},
                direction=f.get("direction"),
                scope=f.get("scope"),
                certainty=f.get("certainty"),
                metric_label=f.get("metric_label"),
                segment=f.get("segment"),
            )
        )
    return facts, missing


def get_provider(logger: CallLogger | None = None) -> LLMProvider:
    name = os.environ.get("LLM_PROVIDER") or load("llm")["provider"]
    if name == "fake":
        from sr.llm.fake import FakeLLMProvider

        return FakeLLMProvider(logger=logger)
    if name == "anthropic":
        from sr.llm.anthropic import ClaudeProvider

        return ClaudeProvider(logger=logger)
    raise ValueError(f"unknown LLM provider {name!r}")
