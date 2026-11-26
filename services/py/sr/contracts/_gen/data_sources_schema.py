# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class Kind(StrEnum):
    market_data = "market_data"
    filing = "filing"
    insider_filing = "insider_filing"
    company_ir = "company_ir"
    news = "news"
    policy = "policy"
    court = "court"
    expectation = "expectation"
    macro = "macro"
    options = "options"
    llm = "llm"


class LicenseScope(StrEnum):
    public = "public"
    licensed_internal = "licensed_internal"
    licensed_display = "licensed_display"
    restricted = "restricted"


class VerificationStatus(StrEnum):
    proposed = "proposed"
    sample_verified = "sample_verified"
    contracted = "contracted"
    retired = "retired"


class DataSources(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    source_id: str
    kind: Kind
    provider: str
    license_scope: LicenseScope
    verification_status: VerificationStatus
    time_precision_default: common_schema.TimePrecision
    notes: str | None = None
