# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Interval(BaseModel):
    quantiles: dict[str, Any]
    unit: str
    validated: bool


class SigmaHatPp(RootModel[float]):
    root: float = Field(..., ge=0.0)


class ThresholdPp(RootModel[float]):
    root: float = Field(..., ge=0.0)


class Unit(StrEnum):
    abs_relative_pp = "abs_relative_pp"


class MoveQuantiles(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    p50: float = Field(..., ge=0.0)
    p80: float = Field(..., ge=0.0)
    p90: float = Field(..., ge=0.0)
    unit: Unit


class Scenario(BaseModel):
    outcome: str
    label: str
    evidence_direction: str | None = None


class ThresholdK(RootModel[float]):
    root: float = Field(..., ge=0.0)


class Locked(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    target_definition_version: str
    quote_rule_version: str
    benchmark_version_id: str
    calendar_version: str
    model_version_id: str
    calibration_version: str | None
    schema_version: str
    sigma_model_version: str | None
    sigma_hat_pp: SigmaHatPp | None
    threshold_k: ThresholdK | None
    threshold_pp: ThresholdPp | None
    feature_set_version: str


class Predictions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    prediction_id: str = Field(..., pattern="^pred_")
    run_id: str
    target_row_id: str
    security_id: str
    event_id: str | None = None
    status: common_schema.PredictionStatus
    probabilities: common_schema.Probabilities | None = None
    predicted_class: str | None = None
    interval: Interval | None = None
    sigma_hat_pp: SigmaHatPp | None = None
    threshold_pp: ThresholdPp | None = None
    move_quantiles: MoveQuantiles | None = None
    scenarios: list[Scenario] | None = None
    edge_vs_baseline: float | None = None
    display_tier: common_schema.DisplayTier
    abstain_reason: common_schema.AbstainReason | None = None
    is_primary: bool
    sampling_rule: common_schema.SamplingRule
    schedule_slot_id: str | None = None
    schedule_version: str | None = None
    scheduled_for: common_schema.Timestamp | None = None
    supersedes_prediction_id: str | None = None
    valid_until: common_schema.Timestamp
    locked: Locked = Field(
        ..., description="frozen at publish; immutable after published (DB trigger)"
    )
    t0_quote_id: str | None = None
    t0_benchmark_quote_ids: list[str]
    target_end_at: common_schema.Timestamp | None = None
    published_at: common_schema.Timestamp | None = None
