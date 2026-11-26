# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class CategoryConfidence(RootModel[float]):
    root: float = Field(..., ge=0.0, le=1.0)


class Disposition(StrEnum):
    kept = "kept"
    duplicate = "duplicate"
    excluded_irrelevant = "excluded_irrelevant"
    excluded_after_asof = "excluded_after_asof"
    excluded_restricted = "excluded_restricted"
    pending_review = "pending_review"
    fetch_failed = "fetch_failed"


class Relevance(RootModel[float]):
    root: float = Field(..., ge=0.0, le=1.0)


class CollectionItems(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    item_id: str
    collection_run_id: str
    source_id: str
    channel: common_schema.CollectionChannel
    submission_id: str | None = None
    submitted_by: str | None = None
    category: common_schema.CollectionCategory
    category_confidence: CategoryConfidence | None = None
    title: str
    snippet: str | None = None
    doc_version_id: str | None = None
    mentions: list[str]
    disposition: Disposition
    duplicate_of: str | None = None
    exclusion_reason: str | None = None
    relevance: Relevance | None = None
    linked_event_id: str | None = None
    linked_evidence_ids: list[str]
    occurred_at: common_schema.Timestamp | None = None
    source_published_at: common_schema.Timestamp | None = None
    source_published_precision: common_schema.TimePrecision | None = None
    received_at: common_schema.Timestamp | None = None
    available_at: common_schema.Timestamp | None = None
