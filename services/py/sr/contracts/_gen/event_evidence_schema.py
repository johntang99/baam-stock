# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class EventEvidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    evidence_id: str
    event_id: str
    doc_version_id: str
    claim: str
    claimant: str | None = None
    span: dict[str, Any] = Field(..., description="page/paragraph/char range")
    verification_status: common_schema.EvidenceVerificationStatus
    available_at: common_schema.Timestamp
    visibility: common_schema.Visibility
    independent_origin_key: str
