# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class ActionType(StrEnum):
    split = "split"
    reverse_split = "reverse_split"
    cash_dividend = "cash_dividend"
    special_dividend = "special_dividend"
    spin_off = "spin_off"
    ticker_change = "ticker_change"
    merger_delisting = "merger_delisting"


class CorporateActions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    action_id: str
    security_id: str
    action_type: ActionType
    announced_at: common_schema.Timestamp
    ex_date: common_schema.Date
    effective_at: common_schema.Timestamp | None = None
    ratio: float | None = None
    cash_amount: float | None = None
    source_id: str
    available_at: common_schema.Timestamp
