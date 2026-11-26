# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Status(StrEnum):
    healthy = "healthy"
    degraded = "degraded"
    down = "down"


class LatencyP50Ms(RootModel[float]):
    root: float = Field(..., ge=0.0)


class LatencyP95Ms(RootModel[float]):
    root: float = Field(..., ge=0.0)


class ErrorRate1h(RootModel[float]):
    root: float = Field(..., ge=0.0, le=1.0)


class LicenseScope(StrEnum):
    public = "public"
    licensed_internal = "licensed_internal"
    licensed_display = "licensed_display"
    restricted = "restricted"


class VerificationStatus(StrEnum):
    proposed = "proposed"
    sample_verified = "sample_verified"
    contracted = "contracted"
    retired = "retired"


class DataSourceHealth(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    source_id: str
    checked_at: common_schema.Timestamp
    status: Status
    latency_p50_ms: LatencyP50Ms | None = None
    latency_p95_ms: LatencyP95Ms | None = None
    last_success_at: common_schema.Timestamp | None = None
    error_rate_1h: ErrorRate1h | None = None
    license_scope: LicenseScope
    verification_status: VerificationStatus
    note: str | None = None
