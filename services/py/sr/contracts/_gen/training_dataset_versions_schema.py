# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class TimeRange(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    start: common_schema.Date
    end: common_schema.Date


class Name(StrEnum):
    train = "train"
    calibration = "calibration"
    validation = "validation"
    holdout = "holdout"


class Split(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: Name
    start: common_schema.Date
    end: common_schema.Date
    embargo_days: int = Field(..., ge=0)


class TrainingDatasetVersions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    dataset_version_id: str = Field(..., pattern="^ds_")
    target_id: common_schema.TargetId
    feature_set_version: str
    label_version: str
    source_versions: dict[str, Any]
    time_range: TimeRange
    splits: list[Split]
    availability_check_passed: bool
    n_rows: int = Field(..., ge=0)
    n_trading_days: int = Field(..., ge=0)
    n_event_clusters: int = Field(..., ge=0)
    class_balance: dict[str, Any]
    exclusions: dict[str, Any]
    parent_dataset_version_id: str | None = None
    manifest_path: str
    created_at: common_schema.Timestamp
