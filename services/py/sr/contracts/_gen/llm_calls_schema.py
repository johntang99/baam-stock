# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Purpose(StrEnum):
    extract_facts = "extract_facts"
    draft_explanation = "draft_explanation"


class OutputHash(RootModel[str]):
    root: str = Field(..., pattern="^[0-9a-f]{64}$")


class Mode(StrEnum):
    live = "live"
    replay = "replay"


class Status(StrEnum):
    succeeded = "succeeded"
    rejected_validation = "rejected_validation"
    refused = "refused"
    failed = "failed"


class LatencyMs(RootModel[int]):
    root: int = Field(..., ge=0)


class LlmCalls(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    call_id: str = Field(..., pattern="^llm_")
    purpose: Purpose
    provider: str
    model: str
    prompt_version: str
    prompt_hash: str = Field(..., pattern="^[0-9a-f]{64}$")
    input_hash: str = Field(..., pattern="^[0-9a-f]{64}$")
    output_hash: OutputHash | None = None
    doc_version_id: str | None = None
    mode: Mode
    request_params: dict[str, Any] = Field(
        ...,
        description="effort, max_tokens, output schema id; tools must be [] (no web search)",
    )
    usage: dict[str, Any] = Field(
        ..., description="input_tokens, output_tokens, cache_* as returned"
    )
    stop_reason: str | None = None
    status: Status
    error: common_schema.Error | None = None
    latency_ms: LatencyMs | None = None
    created_at: common_schema.Timestamp
