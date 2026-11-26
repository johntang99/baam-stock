# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class Status(StrEnum):
    open = "open"
    early_close = "early_close"
    closed = "closed"


class TradingSessions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    exchange: common_schema.Exchange
    session_date: common_schema.Date
    status: Status
    open_at: common_schema.Timestamp | None = None
    close_at: common_schema.Timestamp | None = None
    source: str
    calendar_version: str
