# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class TriggerType(StrEnum):
    on_demand = "on_demand"
    scheduled = "scheduled"
    event = "event"
    market_move = "market_move"
    user_supplement = "user_supplement"


class Mode(StrEnum):
    live = "live"
    replay = "replay"
    dry_run = "dry_run"
    supplement = "supplement"


class Status(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class ReusePolicy(StrEnum):
    reuse_if_unchanged = "reuse_if_unchanged"
    force_recompute = "force_recompute"


class PipelineRuns(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    pipeline_run_id: str = Field(..., pattern="^pr_")
    security_ids: list[str]
    target_ids: list[common_schema.TargetId]
    trigger_type: TriggerType
    requested_by: str | None = None
    mode: Mode
    base_run_id: str | None = None
    submission_ids: list[str]
    as_of: common_schema.Timestamp
    status: Status
    reuse_policy: ReusePolicy
    outputs: dict[str, Any]
    started_at: common_schema.Timestamp | None = None
    finished_at: common_schema.Timestamp | None = None
    sla_ms: int = Field(..., ge=0)
    idempotency_key: str
