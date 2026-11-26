# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from . import common_schema


class Brier(RootModel[float]):
    root: float = Field(..., ge=0.0, le=2.0)


class AbsRelativeMovePp(RootModel[float]):
    root: float = Field(..., ge=0.0)


class PredictionSettlements(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    settlement_id: str = Field(..., pattern="^stl_")
    prediction_id: str
    settlement_version: int = Field(..., ge=1)
    start_quote_id: str | None = None
    end_quote_id: str | None = None
    benchmark_start_quote_ids: list[str]
    benchmark_end_quote_ids: list[str]
    stock_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    relative_return_pp: float | None = None
    outcome_class: str | None = None
    hit: bool | None = None
    brier: Brier | None = None
    abs_relative_move_pp: AbsRelativeMovePp | None = None
    pinball_loss: dict[str, Any] | None = None
    quantile_hits: dict[str, Any] | None = None
    event_outcome: str | None = None
    settlement_evidence_ids: list[str]
    public_confirmation_at: common_schema.Timestamp | None = None
    legal_effective_at: common_schema.Timestamp | None = None
    triggered: bool | None = None
    triggered_at: common_schema.Timestamp | None = None
    invalid_reason: common_schema.InvalidReason | None = None
    settled_at: common_schema.Timestamp
    is_reporting_version: bool
    reason_text: str
