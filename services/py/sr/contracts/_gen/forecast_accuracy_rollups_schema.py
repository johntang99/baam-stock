# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Window(StrEnum):
    session = "session"
    rolling_20d = "rolling_20d"
    rolling_60d = "rolling_60d"
    since_live = "since_live"


class ForecastAccuracyRollups(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    security_id: str
    target_id: common_schema.TargetId
    group_key: str
    window: Window
    n_published: int = Field(..., ge=0)
    n_settled: int = Field(..., ge=0)
    n_abstained: int = Field(..., ge=0)
    n_unsettleable: int = Field(..., ge=0)
    hit_rate: float | None = None
    brier: float | None = None
    bss_class_frequency: float | None = None
    coverage_p80: float | None = None
    coverage_p90: float | None = None
    mean_interval_width_pp: float | None = None
    mean_residual_pp: float | None = None
    mean_abs_residual_pp: float | None = None
    calibration_bins: list[dict[str, Any]]
    model_version_ids: list[str]
    computed_at: common_schema.Timestamp
