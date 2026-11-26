# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class CommonCoverage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    n_eligible: int = Field(..., ge=0)
    n_candidate: int = Field(..., ge=0)
    n_comparator: int = Field(..., ge=0)
    n_common: int = Field(..., ge=0)


class GateResult(StrEnum):
    pass_ = "pass"
    fail = "fail"
    inconclusive = "inconclusive"


class ModelEvaluations(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    evaluation_id: str = Field(..., pattern="^eval_")
    candidate_model_version_id: str
    comparator_model_version_id: str
    eval_subset: str
    common_coverage: CommonCoverage
    metrics: dict[str, Any]
    n_independent_days: int = Field(..., ge=0)
    n_event_clusters: int = Field(..., ge=0)
    gate_config_version: str
    gate_result: GateResult
    failed_conditions: list[str]
