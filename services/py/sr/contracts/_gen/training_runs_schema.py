# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Trigger(StrEnum):
    scheduled_weekly = "scheduled_weekly"
    manual = "manual"
    drift = "drift"


class Status(StrEnum):
    queued = "queued"
    building_dataset = "building_dataset"
    training = "training"
    calibrating = "calibrating"
    evaluating = "evaluating"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TrainingRuns(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    training_run_id: str = Field(..., pattern="^tr_")
    dataset_version_id: str
    trigger: Trigger
    parent_model_version_id: str | None = None
    code_version: str
    config_hash: str
    random_seed: int
    status: Status
    stage: str | None = None
    started_at: common_schema.Timestamp | None = None
    finished_at: common_schema.Timestamp | None = None
    error: common_schema.Error | None = None
    artifact_paths: dict[str, Any]
    idempotency_key: str
