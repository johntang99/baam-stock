# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Status(StrEnum):
    ok = "ok"
    timeout = "timeout"
    error = "error"
    skipped = "skipped"


class LatencyMs(RootModel[float]):
    root: float = Field(..., ge=0.0)


class Counts(BaseModel):
    fetched: int | None = Field(None, ge=0)
    kept: int | None = Field(None, ge=0)
    duplicate: int | None = Field(None, ge=0)
    excluded: int | None = Field(None, ge=0)
    pending_review: int | None = Field(None, ge=0)
    failed: int | None = Field(None, ge=0)
    by_channel: dict[str, Any] | None = None
    by_category: dict[str, Any] | None = None


class SourcesPolledItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    source_id: str
    channel: common_schema.CollectionChannel
    status: Status
    items_fetched: int = Field(..., ge=0)
    latency_ms: LatencyMs | None = None


class CollectionRuns(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    collection_run_id: str
    pipeline_run_id: str | None = None
    snapshot_id: str | None = None
    security_id: str
    window_from: common_schema.Timestamp
    window_to: common_schema.Timestamp
    sources_polled: list[SourcesPolledItem]
    counts: Counts = Field(
        ..., description="aggregated from collection_items, never hand-filled"
    )
    started_at: common_schema.Timestamp
    finished_at: common_schema.Timestamp | None = None
