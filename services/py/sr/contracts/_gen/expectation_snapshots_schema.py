# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class AccountingBasis(StrEnum):
    gaap = "gaap"
    non_gaap = "non_gaap"
    company_defined = "company_defined"


class ExpectationType(StrEnum):
    company_guidance = "company_guidance"
    analyst_consensus = "analyst_consensus"
    other_public = "other_public"


class ExpectationSnapshots(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    exp_id: str
    company_id: str
    metric: str
    fiscal_period: str
    value: float | None = None
    range_low: float | None = None
    range_high: float | None = None
    unit: str
    accounting_basis: AccountingBasis
    expectation_type: ExpectationType
    snapshot_as_of: common_schema.Timestamp
    snapshot_precision: common_schema.TimePrecision
    available_at: common_schema.Timestamp
    source_id: str
    revision_of_exp_id: str | None = None
