"""DP 1.21 corporate actions: raw quotes, adjusted settlement across ex_date, unknown ratio, ticker change (AC-37;
D-40; OQ-56). SYNTHETIC data."""

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from sr.events.reaction import persist_quotes, quote_id, quote_row
from sr.marketdata.corporate_actions import adjust_start, back_adjust, record_action, resolve_ticker
from sr.settle.settle import settle, weights_for
from tests.test_reaction_explain import make_quotes, ramp, visible
from tests.test_settle import BMV, LOCKED, setup_models

T0 = datetime(2026, 12, 2, 15, 0, 1, tzinfo=UTC)  # 10:00:01 ET on Wed 2026-12-02
END = datetime(2026, 12, 3, 15, 0, 1, tzinfo=UTC)  # the next session, after a 10:1 split effective 2026-12-03
EX = date(2026, 12, 3)
NVDA = "sec_nvda"


def two_day_quotes(conn, stock_end: float, peer_end: float, as_of: datetime):  # type: ignore[no-untyped-def]
    """Day 1: stock 100, peers 50 (raw). Day 2: stock `stock_end`, peers `peer_end` (raw, synthetic)."""
    w = weights_for(conn, BMV)
    d1 = make_quotes(
        {
            NVDA: ramp(100, 100, T0, T0 + timedelta(seconds=1)),
            **{p: ramp(50, 50, T0, T0 + timedelta(seconds=1)) for p in w},
        },
        T0 - timedelta(minutes=25),
        T0 + timedelta(minutes=2),
    )
    d2 = make_quotes(
        {
            NVDA: ramp(stock_end, stock_end, END, END + timedelta(seconds=1)),
            **{p: ramp(peer_end, peer_end, END, END + timedelta(seconds=1)) for p in w},
        },
        END - timedelta(minutes=25),
        END + timedelta(minutes=2),
    )
    return visible(pd.concat([d1, d2], ignore_index=True), as_of), w


def next_session_prediction(conn, q: pd.DataFrame, w: dict[str, float]) -> str:  # type: ignore[no-untyped-def]
    """A two-day window (as a next_regular_session forecast would have) with its t0 already attached."""
    setup_models(conn)
    conn.execute(
        """insert into prediction_runs (run_id, trigger_type, snapshot_id, feature_snapshot_id, model_version_id, calibration_version,
                      baseline_model_version_id, publish_deadline, published_at, idempotency_key)
                    values ('run_ca', 'scheduled', 'snap_t', 'f', 'mdl_t', 'c', 'mdl_b', %s, %s, 'run_ca')""",
        (T0, T0 - timedelta(seconds=1)),
    )
    t0_rows = q[q["ts"] == pd.Timestamp(T0)]
    rows = [
        quote_row(r, pd.Timestamp(T0), "src_fixture_synthetic", "qr-0.1") for r in t0_rows.to_dict("records")
    ]
    persist_quotes(conn, rows)
    import json

    conn.execute(
        """insert into predictions (prediction_id, run_id, target_row_id, security_id, status, probabilities, predicted_class, sigma_hat_pp,
               threshold_pp, display_tier, is_primary, sampling_rule, valid_until, locked, published_at, t0_quote_id, t0_benchmark_quote_ids, target_end_at)
           values ('pred_ca', 'run_ca', 'tgt_next_regular_session_v1', 'sec_nvda', 'awaiting_settlement', %s, 'outperform', 0.6, 0.15,
                   'internal_shadow', false, 'on_demand', %s, %s, %s, %s, %s, %s)""",
        (
            json.dumps({"outperform": 0.5, "flat": 0.3, "underperform": 0.2}),
            END,
            json.dumps(LOCKED),
            T0 - timedelta(seconds=1),
            quote_id(NVDA, pd.Timestamp(T0)),
            sorted(quote_id(p, pd.Timestamp(T0)) for p in w),
            END,
        ),
    )
    return "pred_ca"


def split(conn, ratio: float | None, sec: str = NVDA, available: datetime | None = None) -> None:  # type: ignore[no-untyped-def]
    record_action(
        conn,
        {
            "security_id": sec,
            "action_type": "split",
            "announced_at": datetime(2026, 11, 20, tzinfo=UTC),
            "ex_date": EX,
            "ratio": ratio,
            "cash_amount": None,
            "source_id": "src_sec_edgar",
            "available_at": available or datetime(2026, 11, 20, 21, tzinfo=UTC),
        },
    )


AS_OF = END + timedelta(minutes=2)


def test_ac37_split_adjusts_the_start_and_keeps_raw_quotes(conn) -> None:  # type: ignore[no-untyped-def]
    q, w = two_day_quotes(
        conn, stock_end=10.2, peer_end=50.5, as_of=AS_OF
    )  # +2 % after a 10:1 split; peers +1 %
    pid = next_session_prediction(conn, q, w)
    split(conn, 10)
    r = settle(conn, pid, q, AS_OF)
    assert r.status == "settled" and r.row is not None
    assert r.row["stock_return_pct"] == pytest.approx(2.0, abs=1e-6)  # 10.2 / (100 / 10) - 1, by hand
    assert (
        r.row["relative_return_pp"] == pytest.approx(1.0, abs=1e-6) and r.row["outcome_class"] == "outperform"
    )
    assert "公司行为调整" in r.row["reason_text"]
    # reference_quotes keep the raw prices (rule ①)
    t0 = conn.execute(
        "select mid from reference_quotes where quote_id = %s", (quote_id(NVDA, pd.Timestamp(T0)),)
    ).fetchone()
    end = conn.execute(
        "select mid from reference_quotes where quote_id = %s", (r.row["end_quote_id"],)
    ).fetchone()
    assert float(t0["mid"]) == pytest.approx(100.0) and float(end["mid"]) == pytest.approx(10.2)


def test_unknown_ratio_is_unsettleable(conn) -> None:  # type: ignore[no-untyped-def]
    q, w = two_day_quotes(conn, 10.2, 50.5, AS_OF)
    pid = next_session_prediction(conn, q, w)
    split(conn, None)
    r = settle(conn, pid, q, AS_OF)
    assert r.status == "unsettleable" and r.row["invalid_reason"] == "corporate_action"  # type: ignore[index]


def test_constituent_with_unknown_ratio_counts_as_missing(conn) -> None:  # type: ignore[no-untyped-def]
    q, w = two_day_quotes(conn, 102.0, 50.5, AS_OF)  # no NVDA action; one peer has an unknown-ratio split
    pid = next_session_prediction(conn, q, w)
    split(conn, None, sec="sec_amd")
    r = settle(conn, pid, q, AS_OF)
    assert r.status == "settled" and r.row["benchmark_return_pct"] == pytest.approx(1.0, abs=1e-6)  # type: ignore[index]


def test_an_action_published_after_settlement_is_not_used(conn) -> None:  # type: ignore[no-untyped-def]
    q, w = two_day_quotes(conn, 10.2, 50.5, AS_OF)
    pid = next_session_prediction(conn, q, w)
    split(conn, 10, available=AS_OF + timedelta(hours=1))  # point in time: unknown at the run
    r = settle(conn, pid, q, AS_OF)
    assert r.row is not None and r.row["stock_return_pct"] == pytest.approx(
        -89.8, abs=1e-6
    )  # raw, unadjusted
    # a later run that knows the action appends a corrected version
    r2 = settle(conn, pid, q, AS_OF + timedelta(hours=2))
    assert r2.settlement_version == 2 and r2.row["stock_return_pct"] == pytest.approx(2.0, abs=1e-6)  # type: ignore[index]


def test_dividend_threshold() -> None:
    small = {"action_id": "ca_s", "action_type": "cash_dividend", "ratio": None, "cash_amount": 0.3}
    big = {"action_id": "ca_b", "action_type": "cash_dividend", "ratio": None, "cash_amount": 1.0}
    assert adjust_start(100.0, [small], 100.0).price == 100.0  # 0.3 % < 0.5 %: ignored
    assert adjust_start(100.0, [big], 100.0).price == 99.0 and adjust_start(100.0, [big], 100.0).applied == (
        "ca_b",
    )
    spin = {"action_id": "ca_x", "action_type": "spin_off", "ratio": None, "cash_amount": None}
    assert adjust_start(100.0, [spin], 100.0).invalid_reason == "corporate_action"
    rev = {"action_id": "ca_r", "action_type": "reverse_split", "ratio": 0.1, "cash_amount": None}
    assert adjust_start(5.0, [rev], 5.0).price == pytest.approx(50.0)


def test_back_adjust_research_prices() -> None:
    s = pd.Series(
        [100.0, 101.0, 10.2, 10.3], index=[date(2026, 12, 1), date(2026, 12, 2), EX, date(2026, 12, 4)]
    )
    a = back_adjust(s, [{"action_type": "split", "ex_date": EX, "ratio": 10, "cash_amount": None}])
    assert list(a.round(6)) == [10.0, 10.1, 10.2, 10.3]
    assert list(s) == [100.0, 101.0, 10.2, 10.3]  # the input (raw) is not modified


def test_ticker_change_resolves_at_point_in_time(conn) -> None:  # type: ignore[no-untyped-def]
    record_action(
        conn,
        {
            "security_id": NVDA,
            "action_type": "ticker_change",
            "announced_at": datetime(2026, 11, 20, tzinfo=UTC),
            "ex_date": EX,
            "ratio": None,
            "cash_amount": None,
            "source_id": "src_sec_edgar",
            "available_at": datetime(2026, 11, 20, tzinfo=UTC),
        },
        new_ticker="NVDX",
    )
    assert resolve_ticker(conn, "NVDA", date(2026, 12, 2)) == NVDA
    assert resolve_ticker(conn, "NVDA", EX) is None
    assert (
        resolve_ticker(conn, "NVDX", EX) == NVDA and resolve_ticker(conn, "NVDX", date(2026, 12, 2)) is None
    )
    with pytest.raises(ValueError):
        record_action(
            conn, {"security_id": NVDA, "action_type": "ticker_change", "ex_date": EX}, new_ticker=None
        )
