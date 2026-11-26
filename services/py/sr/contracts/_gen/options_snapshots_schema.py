# AUTO-GENERATED from packages/contracts/schemas by scripts/gen-py.sh. Do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from . import common_schema


class OptionsSnapshots(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: common_schema.SchemaVersion | None = None
    opt_snap_id: str
    security_id: str
    snapshot_at: common_schema.Timestamp
    expiry: common_schema.Date
    atm_iv: float | None = None
    iv_25d_put: float | None = None
    iv_25d_call: float | None = None
    implied_move_pct: float | None = None
    put_call_volume_ratio: float | None = None
    source_id: str
    available_at: common_schema.Timestamp
