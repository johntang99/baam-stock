# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class IndustryTemplates(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    template_id: common_schema.IndustryTemplate
    version: int = Field(..., ge=1)
    key_metrics_default: list[str]
    event_types_enabled: list[str]
    official_sources_default: dict[str, Any]
    exposure_dimensions: list[str]
