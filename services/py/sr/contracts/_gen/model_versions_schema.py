# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Status(StrEnum):
    candidate = "candidate"
    shadow = "shadow"
    pending_approval = "pending_approval"
    live = "live"
    retired = "retired"
    rejected = "rejected"
    rolled_back = "rolled_back"


class ModelVersions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    model_version_id: str = Field(..., pattern="^mdl_")
    training_run_id: str
    target_id: common_schema.TargetId
    model_family: common_schema.ModelFamily
    param_layers: common_schema.ParamLayers
    scope: dict[str, Any] | None = None
    features: list[str] | None = None
    hyperparams: dict[str, Any] | None = None
    coefficients_path: str | None = None
    calibration_version: str | None = None
    publish_threshold: dict[str, Any] | None = None
    artifact_sha256: str | None = None
    status: Status
