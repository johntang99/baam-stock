# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class TradeCount(RootModel[int]):
    root: int = Field(..., ge=0)


class MarketBars1m(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    security_id: str
    bar_start: common_schema.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(..., ge=0)
    vwap: float | None = None
    trade_count: TradeCount | None = None
    session_type: common_schema.SessionType
    bar_version: int = Field(..., ge=1)
