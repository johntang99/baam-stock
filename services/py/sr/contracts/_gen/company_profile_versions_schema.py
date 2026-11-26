# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class CompanyProfileVersions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    profile_version_id: str
    company_id: str
    version: int = Field(..., ge=1)
    effective_from: common_schema.Timestamp
    key_metrics: list[str]
    exposures: dict[str, Any]
    official_sources: dict[str, Any]
    priority_rules_version: str
    industry_template: common_schema.IndustryTemplate
    valuation_peers: list[str]
