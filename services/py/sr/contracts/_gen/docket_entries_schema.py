# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class EntryType(StrEnum):
    complaint = "complaint"
    motion = "motion"
    order = "order"
    opinion = "opinion"
    judgment = "judgment"
    verdict = "verdict"
    appeal_notice = "appeal_notice"
    settlement = "settlement"
    other = "other"


class DocketEntries(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    docket_entry_id: str
    event_id: str | None = None
    court: str
    case_number: str
    entry_no: int
    entry_type: EntryType
    filed_at: common_schema.Timestamp
    entered_at: common_schema.Timestamp | None = None
    title: str
    doc_version_id: str | None = None
    source_id: str
    available_at: common_schema.Timestamp
