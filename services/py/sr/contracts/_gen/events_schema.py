# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class ProgressStatus(StrEnum):
    pending = "pending"
    outcome_confirmed = "outcome_confirmed"
    effective = "effective"
    terminated = "terminated"


class AnalysisStatus(StrEnum):
    partial = "partial"
    complete = "complete"
    needs_review = "needs_review"


class CurrentAnalysisVersion(RootModel[int]):
    root: int = Field(..., ge=1)


class Events(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    event_id: str
    category: common_schema.EventCategory
    subtype: str | None = None
    identity_key: str
    progress_status: ProgressStatus
    evidence_status: common_schema.EvidenceVerificationStatus
    analysis_status: AnalysisStatus
    current_analysis_version: CurrentAnalysisVersion | None = None
    row_version: int = Field(..., ge=1)
    first_seen_at: common_schema.Timestamp
