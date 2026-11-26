"""Claude implementation of LLMProvider (D-25) using the official anthropic SDK.

- Model / effort from config/llm.yaml (env LLM_MODEL overrides model); credentials resolved by the SDK
  (ANTHROPIC_API_KEY etc.), never passed around or logged.
- Structured output (output_config.format json_schema) — no tools at all, so no web search in live or replay.
- Server-side refusal fallback enabled (beta); refusals are recorded, never treated as empty extractions.
- Every call -> llm_calls via the CallLogger; quotes are verified against the document before use.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import anthropic as sdk

from sr.config import load
from sr.evidence.hashing import sha256_text
from sr.llm.base import (
    EXTRACT_SYSTEM,
    FACTS_SCHEMA,
    CallLogger,
    CallRecord,
    ExplanationDraft,
    ExplanationInputs,
    ExtractionResult,
    ListCallLogger,
    Mode,
    locate_facts,
    prompt_hash,
)


class ClaudeProvider:
    provider = "anthropic"

    def __init__(self, logger: CallLogger | None = None, client: Any | None = None) -> None:
        cfg = load("llm")
        a = cfg["anthropic"]
        self.model: str = os.environ.get("LLM_MODEL") or a["model"]
        self.effort: str = a["effort"]
        self.max_tokens: int = int(a["max_tokens"])
        self.fallbacks: Any = a["fallbacks"]
        self.fallback_beta: str = a["fallback_beta"]
        self.version: str = cfg["prompts"]["extract_facts"]
        if cfg["rules"]["tools_allowed"]:
            raise ValueError("config/llm.yaml rules.tools_allowed must stay empty (no web search, S3§6)")
        self.logger = logger or ListCallLogger()
        self.client: Any = client if client is not None else sdk.Anthropic()

    def _params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "effort": self.effort,
            "tools": [],
            "output_schema": "facts-0.1",
            "fallbacks": self.fallbacks,
        }

    def extract_facts(
        self, doc_text: str, doc_version_id: str | None = None, mode: Mode = "live"
    ) -> ExtractionResult:
        rec = CallRecord(
            purpose="extract_facts",
            provider=self.provider,
            model=self.model,
            prompt_version=self.version,
            prompt_hash=prompt_hash(EXTRACT_SYSTEM, FACTS_SCHEMA, self.version),
            input_hash=sha256_text(doc_text),
            mode=mode,
            request_params=self._params(),
            status="failed",
            doc_version_id=doc_version_id,
        )
        t0 = time.monotonic()
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                betas=[self.fallback_beta],
                fallbacks=self.fallbacks,
                system=EXTRACT_SYSTEM,
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": FACTS_SCHEMA},
                },
                messages=[{"role": "user", "content": f"<document>\n{doc_text}\n</document>"}],
            )
        except sdk.APIStatusError as e:
            rec.error = {"code": f"http_{e.status_code}", "message": str(e.message)[:500]}
            rec.latency_ms = int((time.monotonic() - t0) * 1000)
            self.logger.log(rec)
            return ExtractionResult("failed", (), rec.call_id, (rec.error["message"],))
        except sdk.APIConnectionError as e:
            rec.error = {"code": "connection_error", "message": str(e)[:500]}
            rec.latency_ms = int((time.monotonic() - t0) * 1000)
            self.logger.log(rec)
            return ExtractionResult("failed", (), rec.call_id, ("connection_error",))

        rec.latency_ms = int((time.monotonic() - t0) * 1000)
        rec.stop_reason = resp.stop_reason
        rec.model = getattr(resp, "model", None) or self.model  # model that actually served (fallback)
        usage = getattr(resp, "usage", None)
        rec.usage = {
            k: getattr(usage, k)
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
            if getattr(usage, k, None) is not None
        }
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            rec.status = "refused"
            rec.error = {"code": "refusal", "message": str(getattr(details, "category", None))}
            self.logger.log(rec)
            return ExtractionResult("refused", (), rec.call_id, ("refusal",))
        if resp.stop_reason == "max_tokens":
            rec.error = {"code": "max_tokens", "message": "output truncated"}
            self.logger.log(rec)
            return ExtractionResult("failed", (), rec.call_id, ("max_tokens",))

        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        rec.output_hash = sha256_text(text)
        try:
            raw = json.loads(text)["facts"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            rec.status, rec.error = "failed", {"code": "bad_json", "message": str(e)[:200]}
            self.logger.log(rec)
            return ExtractionResult("failed", (), rec.call_id, ("bad_json",))
        facts, missing = locate_facts(doc_text, raw)
        rec.status = "rejected_validation" if missing else "succeeded"
        self.logger.log(rec)
        return ExtractionResult(rec.status, () if missing else tuple(facts), rec.call_id, tuple(missing))

    def draft_explanation(self, inputs: ExplanationInputs, mode: Mode = "live") -> ExplanationDraft:
        raise NotImplementedError("draft_explanation is implemented with DP 1.09 (market explanation)")
