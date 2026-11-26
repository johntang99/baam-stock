# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class AnalysisKind(StrEnum):
    flash = "flash"
    full = "full"


class MarketReaction(BaseModel):
    ref_before_quote_id: str | None = None
    ref_asof_quote_id: str | None = None
    stock_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    relative_return_pp: float | None = None
    missing_reason: str | None = None


class MarketExplanation(BaseModel):
    status: common_schema.ExplanationStatus
    observed_facts: list[common_schema.Statement]
    possible_drivers: list[common_schema.Statement]
    counter_evidence: list[common_schema.Statement]
    unexplained: list[common_schema.Statement | str]
    concurrent_events: list[common_schema.Statement | str] | None = None
    valuation_context: dict[str, Any] | None = None


class Kind(StrEnum):
    market_fact = "market_fact"
    timing_check = "timing_check"
    evidence_fact = "evidence_fact"
    attribution = "attribution"
    counter_check = "counter_check"
    analogue = "analogue"
    gap = "gap"
    conclusion = "conclusion"


class Confidence(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class ReasoningTraceItem(BaseModel):
    step: int = Field(..., ge=1)
    kind: Kind
    inputs: dict[str, Any]
    rule: str | None = None
    conclusion: str
    confidence: Confidence | None = None


class EventAnalysisVersions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    analysis_id: str = Field(..., pattern="^eav_")
    event_id: str
    security_id: str
    analysis_version: int = Field(..., ge=1)
    analysis_kind: AnalysisKind
    analysis_as_of: common_schema.Timestamp
    published_at: common_schema.Timestamp | None = None
    evidence_ids: list[str] | None = None
    facts: list[dict[str, Any]] | None = None
    expectation_comparison: dict[str, Any] | None = None
    missing_reason: str | None = None
    impact: list[dict[str, Any]] | None = None
    priority: dict[str, Any] | None = None
    market_reaction: MarketReaction | None = None
    market_explanation: MarketExplanation
    reasoning_trace: list[ReasoningTraceItem] | None = None
    historical_cases: dict[str, Any] | None = None
    scenarios: list[dict[str, Any]] | None = None
    data_gaps: list[str] | None = None
    rule_version: str | None = None
    model_versions: dict[str, Any] | None = None
    prediction_readiness: common_schema.PredictionReadiness
    supersedes_analysis_id: str | None = None
