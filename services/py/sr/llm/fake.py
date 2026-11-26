"""Deterministic fake provider for tests and offline runs. Canned outputs can be registered per document hash
(including deliberately wrong ones, to test the validator); otherwise a tiny regex extractor finds
"<metric> of $X billion" statements."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from sr.config import load
from sr.evidence.hashing import sha256_text
from sr.llm.base import (
    EXTRACT_SYSTEM,
    FACTS_SCHEMA,
    CallLogger,
    CallRecord,
    CallStatus,
    ExplanationDraft,
    ExplanationInputs,
    ExtractionResult,
    ListCallLogger,
    Mode,
    locate_facts,
    prompt_hash,
)

_PATTERN = re.compile(
    r"(?P<metric>revenue|net income|gross margin|data center revenue)[^.$%]*?"
    r"(?:of|was|were)\s+(?P<cur>\$)?(?P<num>\d+(?:\.\d+)?)\s*(?P<scale>billion|million|%)?",
    re.IGNORECASE,
)


class FakeLLMProvider:
    provider = "fake"
    model = "fake-extractor-0.1"

    def __init__(
        self, logger: CallLogger | None = None, canned: dict[str, list[dict[str, Any]]] | None = None
    ) -> None:
        self.logger = logger or ListCallLogger()
        self.canned = canned or {}
        self.version = load("llm")["prompts"]["extract_facts"]

    def register(self, doc_text: str, facts: list[dict[str, Any]]) -> None:
        self.canned[sha256_text(doc_text)] = facts

    def _regex(self, text: str) -> list[dict[str, Any]]:
        out = []
        for m in _PATTERN.finditer(text):
            scale = (m.group("scale") or "").lower()
            unit = {"billion": "USD_billion", "million": "USD_million", "%": "pct"}.get(scale, "number")
            out.append(
                {
                    "metric": m.group("metric").lower().replace(" ", "_"),
                    "value": float(m.group("num")),
                    "unit": unit,
                    "currency": "USD" if m.group("cur") else None,
                    "period": None,
                    "basis": None,
                    "quote": m.group(0),
                }
            )
        return out

    def extract_facts(
        self, doc_text: str, doc_version_id: str | None = None, mode: Mode = "live"
    ) -> ExtractionResult:
        t0 = time.monotonic()
        raw = self.canned.get(sha256_text(doc_text))
        raw = self._regex(doc_text) if raw is None else raw
        facts, missing = locate_facts(doc_text, raw)
        status: CallStatus = "rejected_validation" if missing else "succeeded"
        rec = CallRecord(
            purpose="extract_facts",
            provider=self.provider,
            model=self.model,
            prompt_version=self.version,
            prompt_hash=prompt_hash(EXTRACT_SYSTEM, FACTS_SCHEMA, self.version),
            input_hash=sha256_text(doc_text),
            mode=mode,
            request_params={"tools": []},
            status=status,
            doc_version_id=doc_version_id,
            output_hash=sha256_text(json.dumps(raw, sort_keys=True)),
            stop_reason="end_turn",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
        self.logger.log(rec)
        return ExtractionResult(status, () if missing else tuple(facts), rec.call_id, tuple(missing))

    def draft_explanation(self, inputs: ExplanationInputs, mode: Mode = "live") -> ExplanationDraft:
        # Phase 1 group 2 (DP 1.09) fills this in; the fake only echoes cited statements.
        v = load("llm")["prompts"]["draft_explanation"]
        rec = CallRecord(
            purpose="draft_explanation",
            provider=self.provider,
            model=self.model,
            prompt_version=v,
            prompt_hash=sha256_text(v),
            input_hash=sha256_text(json.dumps(inputs.statements, sort_keys=True)),
            mode=mode,
            request_params={"tools": []},
            status="succeeded",
        )
        self.logger.log(rec)
        cited = tuple(s for s in inputs.statements if s.get("evidence_ids") or s.get("quote_ids"))
        return ExplanationDraft("succeeded", cited, (), rec.call_id)
