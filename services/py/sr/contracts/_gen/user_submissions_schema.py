# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class InputKind(StrEnum):
    link = "link"
    text = "text"
    file = "file"


class SystemCategory(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    category: common_schema.CollectionCategory
    confidence: float = Field(..., ge=0.0, le=1.0)


class Status(StrEnum):
    received = "received"
    fetching = "fetching"
    verifying = "verifying"
    verified_primary = "verified_primary"
    media_level = "media_level"
    unverified = "unverified"
    duplicate = "duplicate"
    rejected_restricted = "rejected_restricted"
    fetch_failed = "fetch_failed"


class Check1(StrEnum):
    link_reachable = "link_reachable"
    domain_reputation = "domain_reputation"
    origin_traced = "origin_traced"
    content_matches_origin = "content_matches_origin"
    timestamp_consistent = "timestamp_consistent"
    duplicate_check = "duplicate_check"
    mnpi_screen = "mnpi_screen"


class Result(StrEnum):
    pass_ = "pass"
    fail = "fail"
    n_a = "n_a"


class Check(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    check: Check1
    result: Result
    note: str | None = None


class Verification(BaseModel):
    fetched_ok: bool | None = None
    http_status: int | None = None
    canonical_url: str | None = None
    origin_source_id: str | None = None
    origin_url: str | None = None
    origin_published_at: common_schema.Timestamp | None = None
    independent_origin_key: str | None = None
    content_hash: str | None = None
    duplicate_of_item_id: str | None = None
    checks: list[Check] | None = None


class Visibility(StrEnum):
    submitter_and_reviewers = "submitter_and_reviewers"
    shared = "shared"


class UserSubmissions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    submission_id: str = Field(..., pattern="^sub_")
    submitted_by: str
    security_ids: list[str]
    input_kind: InputKind
    url: str | None = None
    text: str | None = None
    file_path: str | None = None
    user_note: str | None = None
    user_categories: list[str]
    system_categories: list[SystemCategory]
    final_categories: list[str]
    submitted_at: common_schema.Timestamp
    status: Status
    verification: Verification = Field(
        ..., description="see DC §3.2 user_submissions.verification"
    )
    item_id: str | None = None
    missed_by_system: bool | None = None
    supplement_run_id: str | None = None
    visibility: Visibility
