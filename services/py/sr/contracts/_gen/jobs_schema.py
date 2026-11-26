# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class JobType(StrEnum):
    ingest_doc = "ingest_doc"
    analyze_event = "analyze_event"
    build_snapshot = "build_snapshot"
    run_forecast = "run_forecast"
    settle_due = "settle_due"
    replay_day = "replay_day"
    build_dataset = "build_dataset"
    train = "train"
    evaluate = "evaluate"
    shadow_score = "shadow_score"
    pipeline_step = "pipeline_step"
    onboarding_step = "onboarding_step"
    source_healthcheck = "source_healthcheck"


class Status(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    retry_wait = "retry_wait"
    dead = "dead"


class Jobs(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    job_id: str = Field(..., pattern="^job_")
    job_type: JobType
    pipeline_run_id: str | None = None
    onboarding_id: str | None = None
    payload: dict[str, Any]
    idempotency_key: str
    status: Status
    attempts: int = Field(..., ge=0)
    max_attempts: int = Field(..., ge=1)
    run_after: common_schema.Timestamp
    locked_by: str | None = None
    locked_at: common_schema.Timestamp | None = None
    last_error: str | None = None
