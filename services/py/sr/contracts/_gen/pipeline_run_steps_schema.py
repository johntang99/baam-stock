# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Step(StrEnum):
    collect_evidence = "collect_evidence"
    verify_dedupe = "verify_dedupe"
    analyze_events = "analyze_events"
    build_snapshot = "build_snapshot"
    readiness_check = "readiness_check"
    infer = "infer"
    publish = "publish"
    schedule_settlement = "schedule_settlement"


class Status(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    skipped = "skipped"
    failed = "failed"
    retry_wait = "retry_wait"


class PipelineRunSteps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    pipeline_run_id: str
    step_no: int = Field(..., ge=1)
    step: Step
    security_id: str
    status: Status
    attempt: int = Field(..., ge=0)
    started_at: common_schema.Timestamp | None = None
    finished_at: common_schema.Timestamp | None = None
    detail: dict[str, Any]
    error: common_schema.Error | None = None
    job_id: str | None = None
