"""DP 1.15 settlement: direction + move, idempotent, append-only versions (AC-14, AC-15, AC-27; OQ-49). SYNTHETIC."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import pytest

from sr.forecast.publish import attach_t0
from sr.settle.settle import quality_summary, settle, weights_for
from sr.timeguard import LookaheadError
from tests.test_reaction_explain import make_quotes, ramp, visible

P = datetime(2026, 12, 2, 15, 0, tzinfo=UTC)  # 10:00 ET publish
NVDA = "sec_nvda"
BMV = "bmv_semis_peer_ex_nvda_v1"
LOCKED = {
    "target_definition_version": "td-0.2",
    "quote_rule_version": "qr-0.1",
    "benchmark_version_id": BMV,
    "calendar_version": "cal",
    "model_version_id": "mdl_t",
    "calibration_version": "c",
    "schema_version": "contract-0.7.3",
    "sigma_model_version": "sigma-0.1",
    "sigma_hat_pp": 0.6,
    "threshold_k": 0.25,
    "threshold_pp": 0.15,
    "feature_set_version": "fs-0.2",
}


def setup_models(conn) -> None:  # type: ignore[no-untyped-def]
    conn.execute("""insert into training_dataset_versions (dataset_version_id, target_id, feature_set_version, label_version,
                      source_versions, time_range, splits, availability_check_passed, n_rows, n_trading_days, n_event_clusters,
                      class_balance, exclusions, manifest_path)
                    values ('ds_t', 'regular_60m', 'fs-0.2', 'lbl-0.1', '{}', '{}', '[]', true, 0, 0, 0, '{}', '{}', 'synthetic')""")
    conn.execute("""insert into training_runs (training_run_id, dataset_version_id, trigger, code_version, config_hash, random_seed,
                      status, idempotency_key) values ('tr_t', 'ds_t', 'manual', 't', 't', 1, 'completed', 'tr_t')""")
    conn.execute("""insert into model_versions (model_version_id, training_run_id, target_id, model_family, param_layers)
                    values ('mdl_t', 'tr_t', 'regular_60m', 'market_logit', 'market'), ('mdl_b', 'tr_t', 'regular_60m', 'class_frequency', 'market')""")
    conn.execute(
        """insert into security_state_snapshots (snapshot_id, security_id, trigger_type, analysis_as_of, evidence_watermark,
                      market_watermark, market_state, session_date, benchmark_version_id, new_catalyst_found, explanation_status,
                      explanation_summary, data_quality, run_state, valid_until, prediction_readiness, dedupe_key, published_at)
                    values ('snap_t', 'sec_nvda', 'scheduled', %s, %s, %s, 'regular', '2026-12-02', %s, false, 'partial', 'synthetic',
                      'ok', 'complete', %s, '{}', 'k_t', %s)""",
        (P, P, P, BMV, P + timedelta(minutes=10), P),
    )


def make_prediction(
    conn, n: int, move: bool = False, probs: dict[str, float] | None = None, status: str = "published"
) -> str:  # type: ignore[no-untyped-def]
    run = f"run_t{n}"
    conn.execute(
        """insert into prediction_runs (run_id, trigger_type, snapshot_id, feature_snapshot_id, model_version_id,
                      calibration_version, baseline_model_version_id, publish_deadline, published_at, idempotency_key)
                    values (%s, 'scheduled', 'snap_t', 'f', 'mdl_t', 'c', 'mdl_b', %s, %s, %s)""",
        (run, P, P, run),
    )
    pid = f"pred_t{n}"
    probs = probs or {"outperform": 0.5, "flat": 0.3, "underperform": 0.2}
    vals: dict[str, Any] = {
        "prediction_id": pid,
        "run_id": run,
        "security_id": NVDA,
        "status": status,
        "display_tier": "internal_shadow",
        "is_primary": False,
        "sampling_rule": "on_demand",
        "valid_until": P + timedelta(hours=1),
        "locked": json.dumps(LOCKED),
        "published_at": P,
    }
    if move:
        vals |= {
            "target_row_id": "tgt_regular_60m_move_v1",
            "move_quantiles": json.dumps({"p50": 0.3, "p80": 0.6, "p90": 0.8, "unit": "abs_relative_pp"}),
        }
    elif status == "abstained":
        vals |= {"target_row_id": "tgt_regular_60m_v1", "abstain_reason": "insufficient_data"}
    else:
        vals |= {
            "target_row_id": "tgt_regular_60m_v1",
            "probabilities": json.dumps(probs),
            "predicted_class": max(probs, key=probs.get),
            "sigma_hat_pp": 0.6,
            "threshold_pp": 0.15,
        }
    cols = list(vals)
    conn.execute(
        f"insert into predictions ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
        [vals[c] for c in cols],
    )
    return pid


def quotes(
    conn,
    stock_ret: float,
    peer_ret: float,
    until: datetime | None = None,
    drop_peers: int = 0,
    halt: bool = False,
) -> pd.DataFrame:  # type: ignore[no-untyped-def]
    """Stock 100 and peers 50 flat until t0 (P + 1 s), then linear to the given % at t0 + 60 min (synthetic)."""
    w = weights_for(conn, BMV)
    t0, end = P + timedelta(seconds=1), P + timedelta(minutes=60, seconds=1)
    paths = {NVDA: ramp(100, 100 * (1 + stock_ret / 100), t0, end)}
    peers = list(w)[drop_peers:]
    paths |= {p: ramp(50, 50 * (1 + peer_ret / 100), t0, end) for p in peers}
    as_of = until or end + timedelta(minutes=2)
    q = make_quotes(paths, P - timedelta(minutes=25), as_of)
    if drop_peers:  # the dropped peers do have quotes until 10 minutes before the end
        q2 = make_quotes(
            {p: ramp(50, 50, t0, end) for p in list(w)[:drop_peers]},
            P - timedelta(minutes=25),
            end - timedelta(minutes=10),
        )
        q = pd.concat([q, q2], ignore_index=True)
    if halt:
        h = (
            (q["security_id"] == NVDA)
            & (q["ts"] >= pd.Timestamp(P + timedelta(minutes=20)))
            & (q["ts"] < pd.Timestamp(P + timedelta(minutes=23)))
        )
        q.loc[h, "halted"] = True
    return visible(q, as_of)


DUE = P + timedelta(minutes=62, seconds=1)


# ---------------------------------------------------------------- AC-14: five hand-calculated settlements
@pytest.mark.parametrize(
    ("stock", "peer", "probs", "outcome", "hit", "brier"),
    [
        (
            1.0,
            0.5,
            {"outperform": 0.5, "flat": 0.3, "underperform": 0.2},
            "outperform",
            True,
            0.25 + 0.09 + 0.04,
        ),
        (
            -0.2,
            0.1,
            {"outperform": 0.5, "flat": 0.3, "underperform": 0.2},
            "underperform",
            False,
            0.25 + 0.09 + 0.64,
        ),
        (0.1, 0.0, {"outperform": 0.2, "flat": 0.6, "underperform": 0.2}, "flat", True, 0.04 + 0.16 + 0.04),
        (
            0.15,
            0.0,
            {"outperform": 0.5, "flat": 0.3, "underperform": 0.2},
            "flat",
            False,
            0.25 + 0.49 + 0.04,
        ),  # boundary is flat
    ],
)
def test_ac14_hand_calculated_direction(conn, stock, peer, probs, outcome, hit, brier) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1, probs=probs)
    r = settle(conn, pid, quotes(conn, stock, peer), DUE)
    assert r.status == "settled" and r.row is not None
    assert r.row["relative_return_pp"] == pytest.approx(stock - peer, abs=1e-6)
    assert r.row["stock_return_pct"] == pytest.approx(stock, abs=1e-6)
    assert (r.row["outcome_class"], r.row["hit"]) == (outcome, hit)
    assert r.row["brier"] == pytest.approx(brier, abs=1e-9)
    p = conn.execute(
        "select status, t0_quote_id from predictions where prediction_id = %s", (pid,)
    ).fetchone()
    assert (
        p["status"] == "settled" and p["t0_quote_id"] == "rq_nvda_20261202_150001"
    )  # t0 attached during settlement
    assert "阈值" in r.row["reason_text"]


def test_ac14_hand_calculated_move(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1, move=True)
    r = settle(conn, pid, quotes(conn, 0.6, 0.1), DUE)
    assert r.status == "settled" and r.row is not None
    assert r.row["abs_relative_move_pp"] == pytest.approx(0.5, abs=1e-6)  # AC-27
    pl = r.row["pinball_loss"]
    assert pl["p50"] == pytest.approx(0.5 * 0.2, abs=1e-6)  # under-forecast by 0.2
    assert pl["p80"] == pytest.approx(0.2 * 0.1, abs=1e-6)  # over by 0.1: (1 - 0.8) × 0.1
    assert pl["p90"] == pytest.approx(0.1 * 0.3, abs=1e-6)  # over by 0.3: (1 - 0.9) × 0.3
    assert r.row["quantile_hits"] == {"p50": False, "p80": True, "p90": True}
    assert r.row["outcome_class"] is None and r.row["brier"] is None


# ---------------------------------------------------------------- idempotency and versions
def test_ac14_three_runs_one_result(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1)
    q = quotes(conn, 1.0, 0.5)
    first = settle(conn, pid, q, DUE)
    again = [settle(conn, pid, q, DUE + timedelta(minutes=i)) for i in (1, 2)]
    assert first.status == "settled" and [a.status for a in again] == ["unchanged", "unchanged"]
    assert {a.settlement_id for a in again} == {first.settlement_id}
    assert conn.execute("select count(*) as n from prediction_settlements").fetchone()["n"] == 1


def test_correction_appends_a_version(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1)
    full = quotes(conn, 1.0, 0.5)
    early = full[
        ~((full["security_id"] == NVDA) & (full["ts"] >= pd.Timestamp(P + timedelta(minutes=60))))
    ]  # end quote not in yet
    v1 = settle(conn, pid, early, DUE)
    assert v1.status == "unsettleable" and v1.row["invalid_reason"] == "no_sync_end_quote"  # type: ignore[index]
    v2 = settle(conn, pid, full, DUE + timedelta(minutes=5))  # the delayed quotes have arrived
    assert v2.status == "settled" and v2.settlement_version == 2
    rows = conn.execute(
        "select settlement_version, is_reporting_version, invalid_reason from prediction_settlements order by 1"
    ).fetchall()
    assert [(r["settlement_version"], r["is_reporting_version"]) for r in rows] == [(1, False), (2, True)]
    assert rows[0]["invalid_reason"] == "no_sync_end_quote"  # the old version is kept as it was
    assert (
        conn.execute("select status from predictions where prediction_id = %s", (pid,)).fetchone()["status"]
        == "settled"
    )


# ---------------------------------------------------------------- invalid windows (AC-15)
def test_ac15_halt_is_unsettleable_and_outside_the_hit_rate(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    a = make_prediction(conn, 1)
    b = make_prediction(conn, 2)
    settle(conn, a, quotes(conn, 1.0, 0.5), DUE)  # hit
    r = settle(conn, b, quotes(conn, 1.0, 0.5, halt=True), DUE)
    assert r.status == "unsettleable" and r.row["invalid_reason"] == "halted"  # type: ignore[index]
    assert (
        conn.execute("select status from predictions where prediction_id = %s", (b,)).fetchone()["status"]
        == "unsettleable"
    )
    s = quality_summary(conn, "tgt_regular_60m_v1")
    assert s == {"n_settled": 1, "hit_rate": 1.0, "unsettleable": {"halted": 1}}


def test_basket_missing_at_the_end(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1)
    r = settle(conn, pid, quotes(conn, 1.0, 0.5, drop_peers=2), DUE)
    assert r.status == "unsettleable" and r.row["invalid_reason"] == "no_sync_end_quote"  # type: ignore[index]


def test_no_start_quote(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1)
    q = quotes(conn, 1.0, 0.5)
    q = q[
        ~((q["ts"] > pd.Timestamp(P)) & (q["ts"] <= pd.Timestamp(P + timedelta(seconds=30))))
    ]  # nothing in the t0 window
    r = settle(conn, pid, q, DUE)
    assert r.status == "unsettleable" and r.row["invalid_reason"] == "no_sync_start_quote"  # type: ignore[index]


# ---------------------------------------------------------------- timing guards
def test_not_due_writes_nothing(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1)
    as_of = P + timedelta(minutes=30)
    w = weights_for(conn, BMV)
    attach_t0(conn, pid, quotes(conn, 1.0, 0.5, until=as_of), w, as_of)
    assert settle(conn, pid, quotes(conn, 1.0, 0.5, until=as_of), as_of).status == "not_due"
    assert conn.execute("select count(*) as n from prediction_settlements").fetchone()["n"] == 0


def test_quotes_received_after_the_run_raise(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1)
    with pytest.raises(LookaheadError):
        settle(conn, pid, quotes(conn, 1.0, 0.5), DUE - timedelta(minutes=1, seconds=30))


def test_abstained_prediction_is_not_settled(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1, status="abstained")
    assert settle(conn, pid, quotes(conn, 1.0, 0.5), DUE).status == "not_settleable"
