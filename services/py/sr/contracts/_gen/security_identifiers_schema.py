# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class SecurityIdentifiers(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    security_id: str
    id_type: str = Field(..., pattern="^(ticker|figi|cusip|vendor:[a-z0-9_]+)$")
    value: str
    valid_from: common_schema.Date
    valid_to: common_schema.Date | None = None
