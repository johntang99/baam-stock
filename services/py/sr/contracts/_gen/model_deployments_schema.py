# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class State(StrEnum):
    active = "active"
    rolled_back = "rolled_back"
    superseded = "superseded"


class ModelDeployments(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    deployment_id: str = Field(..., pattern="^dep_")
    target_id: common_schema.TargetId
    scope: dict[str, Any]
    from_model_version_id: str | None = None
    to_model_version_id: str
    approved_by: str
    approval_note: str
    effective_at: common_schema.Timestamp
    audience: common_schema.Audience
    slices: dict[str, Any] | None = None
    state: State
    rollback_reason: str | None = None
