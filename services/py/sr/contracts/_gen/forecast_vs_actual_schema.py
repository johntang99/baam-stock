# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from . import common_schema


class ForecastVsActual(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    prediction_id: str
    security_id: str
    session_date: common_schema.Date
    target_id: common_schema.TargetId
    schedule_slot_id: str | None = None
    t0_at: common_schema.Timestamp | None = None
    target_end_at: common_schema.Timestamp | None = None
    forecast_path: dict[str, Any]
    actual_path: list[dict[str, Any]]
    status: common_schema.PredictionStatus
    outcome_class: str | None = None
    hit: bool | None = None
    brier: float | None = None
    inside_p80: bool | None = None
    inside_p90: bool | None = None
    residual_pp: float | None = None
    abs_move_error_pp: float | None = None
