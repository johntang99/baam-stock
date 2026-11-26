# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class BenchmarkVersions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    benchmark_version_id: str = Field(..., pattern="^bmv_")
    benchmark_id: str
    version: int = Field(..., ge=1)
    effective_from: common_schema.Date
    effective_to: common_schema.Date | None = None
    constituents: list[common_schema.Constituent] = Field(
        ..., description="weights sum to 1"
    )
    sync_tolerance_ms: int = Field(..., ge=0)
    defined_at: common_schema.Timestamp
