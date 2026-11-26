# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from . import common_schema


class SourceDocuments(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    doc_id: str
    source_id: str
    canonical_url: str | None = None
    external_ref: str | None = None
    origin_doc_id: str | None = None
    subject_company_ids: list[str]
