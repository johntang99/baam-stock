"""DP 1.26 schedule replay (AC-52) + forecast_vs_actual and accuracy rollups (AC-53; D-43, D-44; OQ-57). SYNTHETIC."""

from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest

from sr.calendar import get_calendar
from sr.calendar.calendar import et_to_utc
from sr.eval.fva import refresh_fva
from sr.eval.rollups import refresh_rollups
from sr.pipeline.orchestrator import RunContext
from sr.replay.runner import replay_day
from tests.test_dataset import PEERS_ALL, REFS, FrameProvider, synthetic_quotes
from tests.test_forecast import DAY, NVDA, history, models
from tests.test_pipeline import Guarded


@pytest.fixture(scope="module")
def provider() -> FrameProvider:
    return FrameProvider(synthetic_quotes([NVDA, *PEERS_ALL, *REFS], seed=21))


def contexts(conn, provider, tmp_path, late_slot: datetime | None = None):  # type: ignore[no-untyped-def]
    m, h = models(conn, tmp_path), history()
    s = get_calendar().session(DAY)
    assert s.open_at is not None
    first = provider.quotes_1s(list(provider.security_ids), s.open_at - timedelta(minutes=20), s.open_at)
    closes = {
        sid: float((g["bid"].iloc[0] + g["ask"].iloc[0]) / 2)
        for sid, g in first.sort_values("ts").groupby("security_id")
    }

    def ctx(t: datetime) -> RunContext:
        lag = (
            timedelta(seconds=200)
            if late_slot is not None and t == late_slot
            else timedelta(milliseconds=600)
        )
        return RunContext(
            Guarded(provider, t + lag), m, h, prev_close=closes, feature_dir=tmp_path, publish_lag=lag
        )

    return ctx


# ---------------------------------------------------------------- AC-52
def test_ac52_normal_day_six_slots_and_a_late_slot(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    late = et_to_utc(DAY, time(11, 30))
    replay_day(
        conn,
        NVDA,
        DAY,
        contexts(conn, provider, tmp_path, late_slot=late),
        lambda t: Guarded(provider, t),
        out_dir=tmp_path,
    )
    preds = conn.execute("select * from predictions order by scheduled_for, target_row_id").fetchall()
    slots = sorted({p["schedule_slot_id"] for p in preds})
    assert slots == ["s0830_pre_open", "s1000", "s1130", "s1300", "s1430", "s1630_next"]
    assert all(p["is_primary"] and p["sampling_rule"] == "schedule_slot" for p in preds)
    assert sum(p["target_row_id"] == "tgt_regular_60m_v1" for p in preds) == 4  # 10:00, 11:30, 13:00, 14:30
    assert [p["schedule_slot_id"] for p in preds if p["target_row_id"] == "tgt_regular_to_close_v1"] == [
        "s1430"
    ]
    late_rows = [p for p in preds if p["schedule_slot_id"] == "s1130"]
    assert {(p["status"], p["abstain_reason"]) for p in late_rows} == {
        ("abstained", "slot_missed")
    }  # 200 s late: not reissued
    no_model = [
        p for p in preds if p["target_row_id"] in ("tgt_next_regular_session_v1", "tgt_regular_to_close_v1")
    ]
    assert {p["abstain_reason"] for p in no_model} == {"model_not_validated"}


def test_ac52_half_day_uses_only_the_d43_slots(conn, tmp_path) -> None:  # type: ignore[no-untyped-def]
    hd = date(2026, 12, 24)  # Christmas Eve: close 13:00 ET
    s = get_calendar().session(hd)
    assert s.status == "early_close" and s.open_at is not None and s.close_at is not None
    from tests.test_reaction_explain import make_quotes, ramp

    w = [
        f"sec_{t}"
        for t in ["amd", "avgo", "mu", "qcom", "txn", "intc", "adi", "mrvl", "amat", "lrcx", "klac"]
    ]
    paths = {
        NVDA: ramp(100, 101, s.open_at, s.close_at),
        **{p: ramp(50, 50.2, s.open_at, s.close_at) for p in w},
    }
    q = make_quotes(paths, s.open_at - timedelta(minutes=25), s.close_at)
    prov = FrameProvider(
        q.drop(
            columns=[
                c
                for c in q.columns
                if c
                not in (
                    "ts",
                    "security_id",
                    "quote_ts",
                    "received_at",
                    "bid",
                    "ask",
                    "last",
                    "halted",
                    "luld_pause",
                )
            ]
        )
    )
    m, h = models(conn, tmp_path), history()
    closes = {NVDA: 100.0, **{p: 50.0 for p in w}}
    res = replay_day(
        conn,
        NVDA,
        hd,
        lambda t: RunContext(
            Guarded(prov, t + timedelta(milliseconds=600)), m, h, prev_close=closes, feature_dir=tmp_path
        ),
        lambda t: Guarded(prov, t),
        out_dir=tmp_path,
    )
    preds = conn.execute("select schedule_slot_id, target_row_id, scheduled_for from predictions").fetchall()
    assert {p["schedule_slot_id"] for p in preds} == {
        "s0830_pre_open",
        "s1000",
        "s1130",
        "s1630_next",
    }  # s1300 / s1430 skipped
    assert ("s1130", "tgt_regular_to_close_v1") in {
        (p["schedule_slot_id"], p["target_row_id"]) for p in preds
    }
    post = next(p for p in preds if p["schedule_slot_id"] == "s1630_next")
    assert post["scheduled_for"] == et_to_utc(hd, time(13, 30))  # moves to close + 30 min
    assert len(res.pipeline_run_ids) == 4


# ---------------------------------------------------------------- AC-53
@pytest.fixture
def replayed(conn, provider, tmp_path):  # type: ignore[no-untyped-def]
    return replay_day(
        conn, NVDA, DAY, contexts(conn, provider, tmp_path), lambda t: Guarded(provider, t), out_dir=tmp_path
    )


def test_ac53_paths_end_where_they_should(conn, replayed) -> None:  # type: ignore[no-untyped-def]
    rows = conn.execute(
        """select f.*, p.interval, p.move_quantiles, s.relative_return_pp as srel, s.abs_relative_move_pp as smove
             from forecast_vs_actual f join predictions p using (prediction_id)
             join prediction_settlements s on s.prediction_id = f.prediction_id and s.is_reporting_version
            where f.status = 'settled'"""
    ).fetchall()
    assert rows
    for r in rows:
        end = r["forecast_path"]["points"][-1]
        assert end["min"] == 60 and r["forecast_path"]["method"] == "sqrt_time_v1"
        if r["target_id"] == "regular_60m":
            q = r["interval"]["quantiles"]
            assert (end["p10"], end["p50"], end["p90"]) == pytest.approx(
                (q["p10"], q["p50"], q["p90"]), abs=1e-9
            )
            rel = float(r["srel"])
            assert float(r["residual_pp"]) == pytest.approx(rel - q["p50"], abs=1e-9)  # by hand
            assert r["inside_p80"] == (q["p10"] <= rel <= q["p90"]) and r["inside_p90"] == (
                q["p05"] <= rel <= q["p95"]
            )
        else:
            mq = r["move_quantiles"]
            assert (end["p50"], end["p80"], end["p90"]) == pytest.approx(
                (mq["p50"], mq["p80"], mq["p90"]), abs=1e-9
            )
            assert float(r["abs_move_error_pp"]) == pytest.approx(float(r["smove"]) - mq["p50"], abs=1e-9)
            assert r["inside_p80"] == (float(r["smove"]) <= mq["p80"])
        last = r["actual_path"][-1]
        assert last["min"] == 60 and abs(last["relative_pp"] - float(r["srel"])) < 1e-9  # AC-53: < 1e-9
        mid = r["forecast_path"]["points"][6]  # 30 min: sqrt(1/2) of the end
        assert mid["min"] == 30 and mid["p50"] == pytest.approx(end["p50"] * (0.5**0.5), abs=1e-9)


def test_ac53_actual_path_never_shows_later_data(conn, provider, replayed) -> None:  # type: ignore[no-untyped-def]
    slot = et_to_utc(DAY, time(10, 0))
    pid = conn.execute(
        "select prediction_id from predictions where schedule_slot_id = 's1000' and target_row_id = 'tgt_regular_60m_v1'"
    ).fetchone()["prediction_id"]
    mid_window = slot + timedelta(minutes=30)
    refresh_fva(conn, Guarded(provider, mid_window), mid_window, [pid])
    r = conn.execute(
        "select actual_path, outcome_class from forecast_vs_actual where prediction_id = %s", (pid,)
    ).fetchone()
    assert (
        max(x["min"] for x in r["actual_path"]) <= 30 and r["outcome_class"] is None
    )  # not settled yet at 10:30


def test_ac53_rollups_count_like_the_settlement_table(conn, replayed) -> None:  # type: ignore[no-untyped-def]
    roll = conn.execute("""select * from forecast_accuracy_rollups where security_id = 'sec_nvda' and target_id = 'regular_60m'
                           and group_key = 'all' and "window" = 'session'""").fetchone()
    n_settled = conn.execute(
        """select count(*) as n from prediction_settlements s join predictions p using (prediction_id)
            where s.is_reporting_version and s.invalid_reason is null and p.target_row_id = 'tgt_regular_60m_v1' and p.is_primary"""
    ).fetchone()["n"]
    assert roll["n_settled"] == n_settled and roll["n_published"] == 4
    assert roll["hit_rate"] is None and roll["brier"] is None  # n < 30: counts only (样本不足)
    slots = {
        r["group_key"]
        for r in conn.execute(
            "select group_key from forecast_accuracy_rollups where target_id = 'regular_60m'"
        ).fetchall()
    }
    assert {"all", "slot:s1000", "slot:s1430"} <= slots


def test_ac53_metrics_once_enough_have_settled(conn) -> None:  # type: ignore[no-untyped-def]
    from sr.eval.rollups import metrics

    rows = [
        {
            "status": "settled",
            "invalid_reason": None,
            "probabilities": {"outperform": 0.6, "flat": 0.3, "underperform": 0.1},
            "predicted_class": "outperform",
            "outcome_class": "outperform" if i % 2 else "flat",
            "hit": bool(i % 2),
            "brier": 0.26 if i % 2 else 0.86,
            "inside_p80": i % 5 != 0,
            "inside_p90": True,
            "residual_pp": 0.1,
            "abs_move_error_pp": None,
            "interval": {"quantiles": {"p10": -0.2, "p90": 0.2}},
            "move_quantiles": None,
        }
        for i in range(30)
    ]
    m = metrics(rows, {"outperform": 1 / 3, "flat": 1 / 3, "underperform": 1 / 3})
    assert m["n_settled"] == 30 and m["hit_rate"] == pytest.approx(0.5) and m["brier"] == pytest.approx(0.56)
    assert m["coverage_p80"] == pytest.approx(0.8) and m["mean_interval_width_pp"] == pytest.approx(0.4)
    assert m["calibration_bins"] == [{"p_low": 0.6, "p_high": 0.7, "n": 30, "observed": 0.5}]
    assert m["bss_class_frequency"] is not None


def test_ac53_refresh_never_changes_predictions(conn, provider, replayed) -> None:  # type: ignore[no-untyped-def]
    before = [dict(r) for r in conn.execute("select * from predictions order by prediction_id").fetchall()]
    t = get_calendar().session(DAY).close_at + timedelta(minutes=10)  # type: ignore[operator]
    refresh_fva(conn, Guarded(provider, t), t)
    refresh_rollups(conn, t)
    after = [dict(r) for r in conn.execute("select * from predictions order by prediction_id").fetchall()]
    assert before == after
    assert pd.Timestamp(t)  # tz-aware
