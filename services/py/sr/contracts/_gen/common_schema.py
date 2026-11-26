# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel


class Common(RootModel[Any]):
    root: Any = Field(
        ...,
        description="Shared definitions for contract-0.7.2 (DATA_CONTRACT §1).",
        title="common",
    )


class SchemaVersion(RootModel[Literal["contract-0.7.2"]]):
    root: Literal["contract-0.7.2"]


class Timestamp(RootModel[AwareDatetime]):
    root: AwareDatetime = Field(..., description="UTC ISO-8601 with Z suffix (DC §1)")


class Date(RootModel[date]):
    root: date = Field(..., title="IsoDate")


class TimePrecision(StrEnum):
    ms = "ms"
    s = "s"
    minute = "minute"
    hour = "hour"
    day = "day"
    unknown = "unknown"


class Visibility(StrEnum):
    public = "public"
    internal = "internal"
    restricted_review = "restricted_review"


class MarketState(StrEnum):
    pre_market = "pre_market"
    regular = "regular"
    post_market = "post_market"
    closed = "closed"
    halted = "halted"


class SessionType(StrEnum):
    pre_market = "pre_market"
    regular = "regular"
    post_market = "post_market"


class TriggerType(StrEnum):
    scheduled = "scheduled"
    event = "event"
    market_move = "market_move"
    on_demand = "on_demand"
    session_check = "session_check"
    user_supplement = "user_supplement"


class TargetId(StrEnum):
    regular_60m = "regular_60m"
    regular_60m_move = "regular_60m_move"
    regular_to_close = "regular_to_close"
    next_regular_session = "next_regular_session"
    overnight_gap = "overnight_gap"
    event_outcome = "event_outcome"


class CoverageTier(StrEnum):
    pilot = "pilot"
    batch2 = "batch2"
    peer_only = "peer_only"
    reference = "reference"
    inactive = "inactive"


class Exchange(StrEnum):
    XNAS = "XNAS"
    XNYS = "XNYS"
    ARCX = "ARCX"
    XCBO = "XCBO"


class IndustryTemplate(StrEnum):
    semiconductor = "semiconductor"
    bank = "bank"
    biotech = "biotech"
    generic = "generic"


class ExplanationStatus(StrEnum):
    supported = "supported"
    partial = "partial"
    insufficient = "insufficient"


class EvidenceVerificationStatus(StrEnum):
    pending = "pending"
    media_report = "media_report"
    primary_confirmed = "primary_confirmed"
    conflicting = "conflicting"
    retracted = "retracted"


class PredictionStatus(StrEnum):
    pending_evaluation = "pending_evaluation"
    published = "published"
    awaiting_trigger = "awaiting_trigger"
    awaiting_settlement = "awaiting_settlement"
    settled = "settled"
    abstained = "abstained"
    not_triggered = "not_triggered"
    unsettleable = "unsettleable"


class AbstainReason(StrEnum):
    insufficient_data = "insufficient_data"
    stale_quote = "stale_quote"
    halted = "halted"
    benchmark_unavailable = "benchmark_unavailable"
    conflicting_facts = "conflicting_facts"
    window_insufficient = "window_insufficient"
    market_closed = "market_closed"
    model_not_validated = "model_not_validated"
    manual_review = "manual_review"
    low_edge = "low_edge"
    slot_missed = "slot_missed"


class InvalidReason(StrEnum):
    no_sync_start_quote = "no_sync_start_quote"
    no_sync_end_quote = "no_sync_end_quote"
    halted = "halted"
    benchmark_unavailable = "benchmark_unavailable"
    corporate_action = "corporate_action"
    source_unverifiable = "source_unverifiable"


class DisplayTier(StrEnum):
    validated_public = "validated_public"
    internal_shadow = "internal_shadow"
    scenario_only = "scenario_only"


class SamplingRule(StrEnum):
    user_supplement = "user_supplement"
    schedule_slot = "schedule_slot"
    scheduled_5m = "scheduled_5m"
    event_first = "event_first"
    market_move_first = "market_move_first"
    on_demand = "on_demand"
    revision = "revision"


class CollectionChannel(StrEnum):
    filing = "filing"
    insider_filing = "insider_filing"
    company_ir = "company_ir"
    news_wire = "news_wire"
    policy = "policy"
    court = "court"
    macro = "macro"
    expectation = "expectation"
    market_data = "market_data"
    peer_company = "peer_company"
    user_submission = "user_submission"


class CollectionCategory(StrEnum):
    earnings_guidance = "earnings_guidance"
    policy_export = "policy_export"
    customer_demand = "customer_demand"
    supply_chain = "supply_chain"
    m_and_a = "m_and_a"
    litigation = "litigation"
    management = "management"
    product = "product"
    capital_return = "capital_return"
    macro = "macro"
    analyst_rating = "analyst_rating"
    insider_trade = "insider_trade"
    market_data = "market_data"
    other = "other"


class EventCategory(StrEnum):
    earnings_guidance = "earnings_guidance"
    customer_demand = "customer_demand"
    policy_export = "policy_export"
    executive_change = "executive_change"
    accounting_audit = "accounting_audit"
    product_supply = "product_supply"
    macro_rates = "macro_rates"
    competition = "competition"
    litigation_regulatory = "litigation_regulatory"
    capital_estimates = "capital_estimates"
    trading_structure = "trading_structure"
    m_and_a = "m_and_a"
    investment_contract = "investment_contract"
    license_policy = "license_policy"


class ModelFamily(StrEnum):
    class_frequency = "class_frequency"
    always_flat = "always_flat"
    persistence = "persistence"
    har_vol = "har_vol"
    market_logit = "market_logit"
    market_event_logit = "market_event_logit"
    gbdt = "gbdt"
    two_stage = "two_stage"


class ParamLayers(StrEnum):
    market = "market"
    market_sector = "market_sector"
    market_sector_company = "market_sector_company"


class Audience(StrEnum):
    internal = "internal"
    selected_v1 = "selected_v1"
    selected_v2 = "selected_v2"
    selected_v3 = "selected_v3"


class Error(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class Status(StrEnum):
    ready = "ready"
    missing_inputs = "missing_inputs"
    manual_review = "manual_review"
    not_applicable = "not_applicable"


class ReadinessItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    status: Status
    reason: str
    analysis_id: str | None = None
    allowed_models: list[str] | None = None


class PredictionReadiness(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    event_outcome: ReadinessItem
    stock_reaction: ReadinessItem


class Probabilities1(RootModel[float]):
    root: float = Field(..., ge=0.0, le=1.0)


class Probabilities(RootModel[dict[str, Probabilities1]]):
    root: dict[str, Probabilities1] = Field(..., min_length=2)


class Constituent(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    security_id: str
    weight: float = Field(..., ge=0.0, le=1.0)


class Statement(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    text: str
    evidence_ids: list[str]
    quote_ids: list[str]
    item_ids: list[str]
    trace_step: int | None = None
