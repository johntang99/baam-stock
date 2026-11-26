# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class PredictionRuns(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    run_id: str = Field(..., pattern="^run_")
    trigger_type: common_schema.TriggerType
    trigger_ref: str | None = None
    snapshot_id: str
    event_analysis_ids: list[str]
    feature_snapshot_id: str
    model_version_id: str
    calibration_version: str
    baseline_model_version_id: str
    evidence_gaps: list[str]
    publish_deadline: common_schema.Timestamp
    published_at: common_schema.Timestamp | None = None
    idempotency_key: str
