# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Subset(StrEnum):
    train = "train"
    calibration = "calibration"
    validation = "validation"
    holdout = "holdout"
    shadow = "shadow"


class Metric(StrEnum):
    log_loss = "log_loss"
    brier = "brier"
    brier_skill_score = "brier_skill_score"
    hit_rate = "hit_rate"
    coverage = "coverage"
    ece = "ece"
    n_effective = "n_effective"
    pinball_loss = "pinball_loss"
    interval_coverage = "interval_coverage"
    interval_width = "interval_width"
    trigger_rate = "trigger_rate"


class ReferenceModel(StrEnum):
    class_frequency = "class_frequency"
    always_flat = "always_flat"
    persistence = "persistence"
    har_vol = "har_vol"


class Denominator(RootModel[int]):
    root: int = Field(..., ge=0)


class TrainingRunMetrics(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    training_run_id: str
    seq: int = Field(..., ge=0)
    stage: str
    iteration: int | None = None
    subset: Subset
    target_id: common_schema.TargetId
    group_key: str
    metric: Metric
    reference_model: ReferenceModel | None = None
    ci95_low: float | None = None
    ci95_high: float | None = None
    value: float
    denominator: Denominator | None = None
    recorded_at: common_schema.Timestamp
