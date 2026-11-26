# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class Severity(StrEnum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Kind(StrEnum):
    source_down = "source_down"
    source_latency = "source_latency"
    quote_stale = "quote_stale"
    pipeline_failed = "pipeline_failed"
    settlement_backlog = "settlement_backlog"
    drift = "drift"
    gate_regression = "gate_regression"
    onboarding_blocked = "onboarding_blocked"


class Alerts(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    alert_id: str
    severity: Severity
    kind: Kind
    ref: str | None = None
    opened_at: common_schema.Timestamp
    acknowledged_by: str | None = None
    resolved_at: common_schema.Timestamp | None = None
    message: str
