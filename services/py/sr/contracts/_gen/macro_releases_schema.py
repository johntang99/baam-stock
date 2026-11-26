# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from . import common_schema


class MacroReleases(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    release_id: str
    series_id: str
    reference_period: str
    vintage_date: common_schema.Date
    value: float
    is_first_release: bool
    release_at: common_schema.Timestamp
    consensus_value: float | None = None
    source_id: str
    available_at: common_schema.Timestamp
