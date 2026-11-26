# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class PriceType(StrEnum):
    nbbo_mid = "nbbo_mid"
    official_close = "official_close"
    official_open = "official_open"
    last_trade = "last_trade"


class QualityFlag(StrEnum):
    stale = "stale"
    wide_spread = "wide_spread"
    halted = "halted"
    luld_pause = "luld_pause"
    crossed = "crossed"
    delayed = "delayed"


class ReferenceQuotes(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    quote_id: str = Field(..., pattern="^rq_")
    security_id: str
    quote_ts: common_schema.Timestamp
    received_at: common_schema.Timestamp
    session_type: common_schema.SessionType
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    last: float | None = None
    spread_bp: float | None = None
    price_type: PriceType
    quality_flags: list[QualityFlag]
    is_qualifying: bool
    quote_rule_version: str
    vendor_source_id: str
    adjustment_basis: str
