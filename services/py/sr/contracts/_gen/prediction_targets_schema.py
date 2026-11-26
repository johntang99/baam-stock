# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Track(StrEnum):
    stock_reaction = "stock_reaction"
    event_outcome = "event_outcome"
    conditional_scenario = "conditional_scenario"


class Type(StrEnum):
    vol_scaled = "vol_scaled"


class OnMissingSigma(StrEnum):
    abstain = "abstain"


class ThresholdRule(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    type: Type
    k: float = Field(..., ge=0.0)
    sigma_model: str
    on_missing_sigma: OnMissingSigma


class OutputKind(StrEnum):
    class_probs = "class_probs"
    quantiles = "quantiles"
    scenarios = "scenarios"


class MinRemainingMin(RootModel[int]):
    root: int = Field(..., ge=0)


class PredictionTargets(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    target_row_id: str = Field(..., pattern="^tgt_")
    target_id: common_schema.TargetId
    target_definition_version: str
    track: Track
    classes: list[str]
    threshold_rule: ThresholdRule | None = None
    output_kind: OutputKind
    window_rule: dict[str, Any]
    min_remaining_min: MinRemainingMin | None = None
    event_id: str | None = None
    question: str | None = None
    deadline_at: common_schema.Timestamp | None = None
    deadline_tz: str | None = None
    confirm_sources: list[str] | None = None
    outcome_resolution: dict[str, Any] | None = None
    no_result_rule: str | None = None
    condition: dict[str, Any] | None = None
    invalid_rules_version: str
