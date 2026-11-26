# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class TargetTier(StrEnum):
    pilot = "pilot"
    batch2 = "batch2"
    peer_only = "peer_only"
    reference = "reference"


class Stage(StrEnum):
    draft = "draft"
    profile_review = "profile_review"
    sources_configured = "sources_configured"
    backfilling = "backfilling"
    data_validated = "data_validated"
    training = "training"
    shadow = "shadow"
    active = "active"
    blocked = "blocked"
    rejected = "rejected"
    paused = "paused"


class Status(StrEnum):
    todo = "todo"
    done = "done"
    failed = "failed"
    waived = "waived"


class ChecklistItem(BaseModel):
    item: str
    status: Status
    evidence: str | None = None


class ParamPolicy(StrEnum):
    market_sector_only = "market_sector_only"
    company_offset_candidate = "company_offset_candidate"


class OnboardingRequests(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    onboarding_id: str = Field(..., pattern="^onb_")
    ticker: str
    cik: str | None = None
    primary_exchange: common_schema.Exchange | None = None
    requested_by: str
    approved_by: str | None = None
    target_tier: TargetTier
    stage: Stage
    checklist: list[ChecklistItem]
    backfill_report: dict[str, Any] | None = None
    param_policy: ParamPolicy
    profile_version_id: str | None = None
    benchmark_version_id: str | None = None
    dataset_version_id: str | None = None
    model_version_id: str | None = None
    blocked_reason: str | None = None
