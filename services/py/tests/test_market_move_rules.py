"""DP 2.03 market-move rules: versioned config, relative-to-basket, volume skipped, cooldown (OQ-59). SYNTHETIC."""

from datetime import date, time, timedelta

import pytest

from sr.calendar.calendar import et_to_utc
from sr.config import load
from sr.snapshot.triggers import MoveScanner, evaluate_rule, rule, rules
from tests.test_reaction_explain import make_quotes, ramp

D = date(2026, 12, 1)
NVDA = "sec_nvda"
PEERS = ["sec_amd", "sec_avgo", "sec_mu"]
W = {p: 1 / 3 for p in PEERS}


def quotes(stock_to: float, basket_to: float, t):  # type: ignore[no-untyped-def]
    a, b = t - timedelta(minutes=10), t - timedelta(minutes=1)
    paths = {NVDA: ramp(100, stock_to, a, b), **{p: ramp(50, 50 * basket_to / 100, a, b) for p in PEERS}}
    q = make_quotes(paths, t - timedelta(minutes=20), t)
    return q[q["received_at"] <= t].reset_index(drop=True)


def test_rules_are_versioned_and_unique() -> None:
    cfg = load("market_move_rules")
    ids = [r["rule_id"] for r in rules()]
    assert cfg["version"].startswith("move_rules-") and len(ids) == len(set(ids))
    assert rule("move_abs_v1")["abs_move_pct"] == 3.0  # the Phase 1 rule is unchanged (OQ-55)


def test_relative_rule_fires_only_against_the_basket() -> None:
    t = et_to_utc(D, time(11, 0))
    alone = quotes(102.5, 100.0, t)  # +2.5 % vs a flat basket: relative hit, absolute no
    r_rel, r_abs = rule("move_rel_basket_v1"), rule("move_abs_v1")
    c = evaluate_rule(r_rel, alone, NVDA, t, weights=W)
    assert c.triggered and c.move_pct == pytest.approx(2.5, abs=0.01) and c.trigger is not None
    assert c.trigger.trigger_type == "market_move" and c.trigger.trigger_ref == "move_rel_basket_v1"
    assert not evaluate_rule(r_abs, alone, NVDA, t).triggered
    sector = quotes(103.5, 103.5, t)  # the whole sector moves: absolute hit, relative no
    assert evaluate_rule(r_abs, sector, NVDA, t).triggered
    assert not evaluate_rule(r_rel, sector, NVDA, t, weights=W).triggered


def test_relative_rule_needs_a_basket_and_regular_hours() -> None:
    t = et_to_utc(D, time(11, 0))
    q = quotes(103.0, 100.0, t)
    assert evaluate_rule(rule("move_rel_basket_v1"), q, NVDA, t).skipped_reason == "no_basket"
    post = et_to_utc(D, time(16, 30))
    qp = quotes(103.0, 100.0, post)
    assert (
        evaluate_rule(rule("move_rel_basket_v1"), qp, NVDA, post, weights=W).skipped_reason
        == "session_not_covered"
    )


def test_volume_rule_is_skipped_without_volume() -> None:
    t = et_to_utc(D, time(11, 0))
    c = evaluate_rule(rule("volume_spike_v1"), quotes(100, 100, t), NVDA, t, weights=W)
    assert not c.triggered and c.skipped_reason == "input_unavailable"


def test_scanner_cooldown() -> None:
    t = et_to_utc(D, time(11, 0))
    sc = MoveScanner()
    first = sc.scan(quotes(103.5, 100.0, t), NVDA, t, weights=W)
    assert {c.rule_id for c in first} == {"move_abs_v1", "move_rel_basket_v1"}
    t2 = t + timedelta(minutes=5)
    assert sc.scan(quotes(103.5, 100.0, t2), NVDA, t2, weights=W) == []  # same move, inside the cooldown
    t3 = t + timedelta(minutes=16)
    assert len(sc.scan(quotes(107.0, 100.0, t3), NVDA, t3, weights=W)) == 2
