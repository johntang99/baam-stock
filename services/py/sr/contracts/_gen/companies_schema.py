# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Cik(RootModel[str]):
    root: str = Field(..., pattern="^\\d{10}$")


class Companies(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    company_id: str = Field(..., pattern="^co_[a-z0-9_]+$")
    legal_name: str
    cik: Cik | None = None
    sector: str
    industry: str
    fiscal_calendar: dict[str, Any] = Field(
        ..., description='{ "fy_end_month": 1, "week_based": true }'
    )
    row_version: int = Field(..., ge=1)
