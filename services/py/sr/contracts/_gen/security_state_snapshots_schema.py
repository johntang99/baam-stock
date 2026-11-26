# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class DataQuality(StrEnum):
    ok = "ok"
    stale = "stale"
    partial = "partial"
    failed = "failed"


class RunState(StrEnum):
    running = "running"
    complete = "complete"
    degraded = "degraded"
    failed = "failed"


class SecurityStateSnapshots(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    snapshot_id: str = Field(..., pattern="^snap_")
    security_id: str
    trigger_type: common_schema.TriggerType
    trigger_ref: str | None = None
    analysis_as_of: common_schema.Timestamp
    evidence_watermark: common_schema.Timestamp
    market_watermark: common_schema.Timestamp
    market_state: common_schema.MarketState
    session_date: common_schema.Date
    last_quote_id: str | None = None
    benchmark_version_id: str
    day_return_pct: float | None = None
    day_relative_pp: float | None = None
    event_analysis_ids: list[str]
    new_catalyst_found: bool
    explanation_status: common_schema.ExplanationStatus
    explanation_summary: str
    data_quality: DataQuality
    run_state: RunState
    quality_issues: list[dict[str, Any]]
    last_valid_at: common_schema.Timestamp | None = None
    valid_until: common_schema.Timestamp
    prediction_readiness: common_schema.PredictionReadiness
    dedupe_key: str
    published_at: common_schema.Timestamp
