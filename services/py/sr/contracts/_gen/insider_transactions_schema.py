# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from . import common_schema


class InsiderTransactions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    txn_id: str
    security_id: str
    insider_name: str
    insider_role: str
    transaction_code: str
    is_10b5_1: bool | None = None
    shares: float
    price: float | None = None
    transaction_date: common_schema.Date
    filed_at: common_schema.Timestamp
    accession_no: str
    available_at: common_schema.Timestamp
