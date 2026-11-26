# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class MilestoneType(StrEnum):
    agreement_signed = "agreement_signed"
    shareholder_vote = "shareholder_vote"
    regulatory_filing = "regulatory_filing"
    regulatory_clearance = "regulatory_clearance"
    closing = "closing"
    termination = "termination"
    complaint_filed = "complaint_filed"
    hearing = "hearing"
    order = "order"
    verdict = "verdict"
    appeal = "appeal"
    settlement = "settlement"
    official_statement = "official_statement"
    proposed_rule = "proposed_rule"
    comment_period_end = "comment_period_end"
    rule_published = "rule_published"
    rule_effective = "rule_effective"
    enforcement_action = "enforcement_action"
    license_applied = "license_applied"
    license_granted = "license_granted"
    license_denied = "license_denied"
    shipment_confirmed = "shipment_confirmed"
    board_announcement = "board_announcement"
    guidance_update = "guidance_update"


class Status(StrEnum):
    scheduled = "scheduled"
    occurred = "occurred"
    delayed = "delayed"
    cancelled = "cancelled"


class EventMilestones(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    milestone_id: str
    event_id: str
    milestone_type: MilestoneType
    decision_body: str | None = None
    expected_at: common_schema.Timestamp | None = None
    actual_at: common_schema.Timestamp | None = None
    status: Status
    evidence_ids: list[str]
