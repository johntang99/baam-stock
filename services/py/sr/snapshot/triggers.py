"""Market-move trigger (DP 1.25; AC-39; MP §3 "异动阈值检测"; OQ-55).

detect_market_move(): |stock mid / reference − 1| >= abs_move_pct, where the reference is the last regular-session
close outside regular hours, and the mid `regular_window_min` earlier inside them. A hit becomes a snapshot trigger
(`trigger_type = market_move`, `trigger_ref = rule_id`). Only quotes received by as_of are considered.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from sr.calendar import get_calendar
from sr.config import load
from sr.snapshot.builder import Trigger, market_state
from sr.timeguard import assert_not_after, ensure_utc


@dataclass(frozen=True)
class MoveCheck:
    triggered: bool
    move_pct: float | None
    reference: str  # "regular_close" | "window_start"
    trigger: Trigger | None = None


def detect_market_move(
    quotes: pd.DataFrame, security_id: str, as_of: datetime, regular_close_mid: float | None = None
) -> MoveCheck:
    """`quotes`: evaluated quotes received by as_of; `regular_close_mid`: the last regular close (extended hours)."""
    cfg = load("snapshot")["market_move"]
    t = ensure_utc(as_of, "as_of")
    assert_not_after(quotes["received_at"], t, "quotes")
    s = quotes[(quotes["security_id"] == security_id) & quotes["mid"].notna()].sort_values("ts")
    s = s[(~s["halted"].astype(bool)) & (~s["luld_pause"].astype(bool))]
    if s.empty:
        return MoveCheck(False, None, "none")
    session = get_calendar().session_for_instant(t.to_pydatetime())
    state = market_state(t.to_pydatetime(), session, None)
    now_mid = float(s.iloc[-1]["mid"])
    if state == "regular":
        start = t - timedelta(minutes=int(cfg["regular_window_min"]))
        before = s[s["ts"] <= start]
        if before.empty:
            return MoveCheck(False, None, "window_start")
        ref, kind = float(before.iloc[-1]["mid"]), "window_start"
    else:
        if regular_close_mid is None:
            return MoveCheck(False, None, "regular_close")
        ref, kind = float(regular_close_mid), "regular_close"
    move = (now_mid / ref - 1.0) * 100.0
    hit = abs(move) >= float(cfg["abs_move_pct"])
    return MoveCheck(
        hit,
        round(move, 6),
        kind,
        Trigger("market_move", str(cfg["rule_id"]), t.to_pydatetime()) if hit else None,
    )
