# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from . import common_schema


class Relation(StrEnum):
    subject = "subject"
    acquirer = "acquirer"
    target = "target"
    supplier = "supplier"
    customer = "customer"
    competitor = "competitor"
    regulated_party = "regulated_party"
    sector_wide = "sector_wide"


class EventSecurityLinks(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    event_id: str
    security_id: str
    relation: Relation
    exposure_note: str | None = None
