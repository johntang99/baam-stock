# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class ArrivalMode(StrEnum):
    live = "live"
    archived = "archived"
    simulated = "simulated"


class SourceDocumentVersions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    doc_version_id: str
    doc_id: str
    version: int = Field(..., ge=1)
    content_hash: str = Field(..., pattern="^[0-9a-f]{64}$")
    storage_path: str | None = None
    locator: str | None = None
    source_published_at: common_schema.Timestamp | None = None
    source_published_precision: common_schema.TimePrecision | None = None
    missing_reason: str | None = None
    received_at: common_schema.Timestamp
    available_at: common_schema.Timestamp
    arrival_mode: ArrivalMode
    simulated_available_at: common_schema.Timestamp | None = None
    is_correction_of: str | None = None
    visibility: common_schema.Visibility
