# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Kind(StrEnum):
    pre_open_outlook = "pre_open_outlook"
    intraday = "intraday"
    post_close_outlook = "post_close_outlook"


class Slot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    slot_id: str = Field(..., pattern="^s\\d{4}")
    time_et: str = Field(..., pattern="^\\d{2}:\\d{2}$")
    kind: Kind
    target_ids: list[common_schema.TargetId]
    start_rule: str


class MissRule(BaseModel):
    grace_s: int = Field(..., ge=0)
    on_miss: str


class ForecastSchedules(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    schedule_id: str
    schedule_version: str
    effective_from: common_schema.Date
    effective_to: common_schema.Date | None = None
    slots: list[Slot]
    half_day_rule: dict[str, Any]
    holiday_rule: str
    miss_rule: MissRule
