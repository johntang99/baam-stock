# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class SecurityType(StrEnum):
    common = "common"
    adr = "adr"
    etf = "etf"
    index = "index"


class Securities(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    security_id: str = Field(..., pattern="^sec_[a-z0-9_]+$")
    company_id: str
    security_type: SecurityType = Field(
        ...,
        description="etf/index added in contract-0.7.1 (reference instruments, D-31)",
    )
    primary_exchange: common_schema.Exchange
    currency: str = Field(..., pattern="^[A-Z]{3}$")
    coverage_tier: common_schema.CoverageTier
    primary_benchmark_id: str | None = None
    reference_benchmark_id: str | None = None
