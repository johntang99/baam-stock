# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from . import common_schema


class Kind(StrEnum):
    peer_basket = "peer_basket"
    etf_reference = "etf_reference"


class BenchmarkDefinitions(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    benchmark_id: str = Field(..., pattern="^bm_")
    kind: Kind
    target_security_id: str | None = None
    methodology: str
    missing_rule: str
