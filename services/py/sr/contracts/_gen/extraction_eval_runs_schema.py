# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class FieldGroup(StrEnum):
    numeric_fact = "numeric_fact"
    direction = "direction"
    scope = "scope"
    certainty = "certainty"


class ExtractionEvalRuns(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    eval_run_id: str
    label_set_version: str
    llm_provider: str
    llm_model: str
    prompt_version: str
    field_group: FieldGroup
    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    f1: float = Field(..., ge=0.0, le=1.0)
    n_docs: int = Field(..., ge=0)
    passed: bool
    created_at: common_schema.Timestamp
