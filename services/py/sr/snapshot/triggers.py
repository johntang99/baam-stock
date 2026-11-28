"""Market-move triggers (DP 1.25, 2.03; AC-39; MP §3 "异动阈值检测"; OQ-55, OQ-59).

Rules are versioned in `config/market_move_rules.yaml`; each hit becomes a snapshot trigger
(`trigger_type = market_move`, `trigger_ref = rule_id`). Only quotes received by as_of are considered.

- `price_abs`: |stock mid / reference − 1| >= abs_move_pct; the reference is the mid `regular_window_min` earlier in
  regular hours and the last regular close outside them (Phase 1 rule `move_abs_v1`, unchanged).
- `relative_to_basket`: |stock return − basket return| over the window >= abs_relative_pp, both read at synchronised
  points (D-06); skipped when the basket is unavailable.
- `volume`: needs a volume column; the NBBO 1-second layer has none yet, so it reports `input_unavailable`.

`MoveScanner` applies the cooldown so a sustained move fires once per rule per `cooldown_min`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sr.benchmark.basket import basket_return
from sr.calendar import get_calendar
from sr.config import load
from sr.events.reaction import sync_points
from sr.snapshot.builder import Trigger, market_state
from sr.timeguard import assert_not_after, ensure_utc


@dataclass(frozen=True)
class MoveCheck:
    triggered: bool
    move_pct: float | None
    reference: str  # "regular_close" | "window_start" | "none"
    trigger: Trigger | None = None
    rule_id: str | None = None
    skipped_reason: str | None = None


def rules() -> list[dict[str, Any]]:
    return list(load("market_move_rules")["rules"])


def rule(rule_id: str) -> dict[str, Any]:
    return next(r for r in rules() if r["rule_id"] == rule_id)


def _clean(quotes: pd.DataFrame, security_id: str) -> pd.DataFrame:
    s = quotes[(quotes["security_id"] == security_id) & quotes["mid"].notna()].sort_values("ts")
    return s[(~s["halted"].astype(bool)) & (~s["luld_pause"].astype(bool))]


def _state(t: pd.Timestamp) -> str:
    session = get_calendar().session_for_instant(t.to_pydatetime())
    return market_state(t.to_pydatetime(), session, None)


def _price_abs(
    r: dict[str, Any],
    quotes: pd.DataFrame,
    security_id: str,
    t: pd.Timestamp,
    regular_close_mid: float | None,
) -> MoveCheck:
    s = _clean(quotes, security_id)
    if s.empty:
        return MoveCheck(False, None, "none", rule_id=r["rule_id"])
    now_mid = float(s.iloc[-1]["mid"])
    if _state(t) == "regular":
        before = s[s["ts"] <= t - timedelta(minutes=int(r["regular_window_min"]))]
        if before.empty:
            return MoveCheck(False, None, "window_start", rule_id=r["rule_id"])
        ref, kind = float(before.iloc[-1]["mid"]), "window_start"
    else:
        if regular_close_mid is None:
            return MoveCheck(False, None, "regular_close", rule_id=r["rule_id"])
        ref, kind = float(regular_close_mid), "regular_close"
    move = (now_mid / ref - 1.0) * 100.0
    hit = abs(move) >= float(r["abs_move_pct"])
    return MoveCheck(
        hit,
        round(move, 6),
        kind,
        Trigger("market_move", str(r["rule_id"]), t.to_pydatetime()) if hit else None,
        r["rule_id"],
    )


def _relative(
    r: dict[str, Any],
    quotes: pd.DataFrame,
    security_id: str,
    t: pd.Timestamp,
    weights: dict[str, float] | None,
) -> MoveCheck:
    if not weights:
        return MoveCheck(False, None, "window_start", rule_id=r["rule_id"], skipped_reason="no_basket")
    stale = pd.Timedelta(seconds=int(load("snapshot")["quality"]["stale_after_s"]))
    start = t - timedelta(minutes=int(r["regular_window_min"]))

    def last_point(at: pd.Timestamp) -> list[Any]:  # only the last sync point is needed: look back 5 s first
        return sync_points(
            quotes, security_id, list(weights), at - pd.Timedelta(seconds=5), at
        ) or sync_points(quotes, security_id, list(weights), at - stale, at)

    a, b = last_point(start), last_point(t)
    if not a or not b:
        return MoveCheck(False, None, "window_start", rule_id=r["rule_id"], skipped_reason="no_sync_point")
    p0, p1 = a[-1], b[-1]
    stock = (float(p1.stock["mid"]) / float(p0.stock["mid"]) - 1.0) * 100.0
    br = basket_return(
        {c: p0.constituents.get(c, {}).get("mid") for c in weights},
        {c: p1.constituents.get(c, {}).get("mid") for c in weights},
        weights,
    )
    if br.status != "ok" or br.return_pct is None:
        return MoveCheck(
            False, None, "window_start", rule_id=r["rule_id"], skipped_reason="benchmark_unavailable"
        )
    rel = stock - br.return_pct
    hit = abs(rel) >= float(r["abs_relative_pp"])
    return MoveCheck(
        hit,
        round(rel, 6),
        "window_start",
        Trigger("market_move", str(r["rule_id"]), t.to_pydatetime()) if hit else None,
        r["rule_id"],
    )


def evaluate_rule(
    r: dict[str, Any],
    quotes: pd.DataFrame,
    security_id: str,
    as_of: datetime,
    regular_close_mid: float | None = None,
    weights: dict[str, float] | None = None,
) -> MoveCheck:
    t = ensure_utc(as_of, "as_of")
    assert_not_after(quotes["received_at"], t, "quotes")
    if _state(t) not in r["sessions"]:
        return MoveCheck(False, None, "none", rule_id=r["rule_id"], skipped_reason="session_not_covered")
    missing = [c for c in r.get("requires", []) if c not in quotes.columns]
    if missing:
        return MoveCheck(False, None, "none", rule_id=r["rule_id"], skipped_reason="input_unavailable")
    if r["kind"] == "price_abs":
        return _price_abs(r, quotes, security_id, t, regular_close_mid)
    if r["kind"] == "relative_to_basket":
        return _relative(r, quotes, security_id, t, weights)
    raise ValueError(f"rule kind {r['kind']!r} has no evaluator")


def detect_market_move(
    quotes: pd.DataFrame, security_id: str, as_of: datetime, regular_close_mid: float | None = None
) -> MoveCheck:
    """Phase 1 entry point: the absolute-move rule `move_abs_v1` only."""
    return evaluate_rule(rule("move_abs_v1"), quotes, security_id, as_of, regular_close_mid)


@dataclass
class MoveScanner:
    """Evaluates every rule and applies the per-(security, rule) cooldown. State is in memory; after a restart the
    queue's idempotency key (security | rule | cooldown bucket) still stops a duplicate snapshot job."""

    last_fired: dict[tuple[str, str], datetime] = field(default_factory=dict)

    def scan(
        self,
        quotes: pd.DataFrame,
        security_id: str,
        as_of: datetime,
        regular_close_mid: float | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[MoveCheck]:
        cool = timedelta(minutes=int(load("market_move_rules")["cooldown_min"]))
        t = ensure_utc(as_of, "as_of").to_pydatetime()
        out = []
        for r in rules():
            c = evaluate_rule(r, quotes, security_id, t, regular_close_mid, weights)
            if not c.triggered:
                continue
            key = (security_id, r["rule_id"])
            last = self.last_fired.get(key)
            if last is not None and t - last < cool:
                continue
            self.last_fired[key] = t
            out.append(c)
        return out


def cooldown_bucket(as_of: datetime) -> str:
    cool = int(load("market_move_rules")["cooldown_min"])
    return ensure_utc(as_of, "as_of").floor(f"{cool}min").isoformat()
