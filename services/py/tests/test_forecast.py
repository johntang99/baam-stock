"""DP 1.14 inference, atomic publish, immutability (AC-13, AC-27 forecast part; D-23, D-41, D-43; OQ-48). SYNTHETIC."""

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg
import pytest

from sr.calendar.calendar import et_to_utc
from sr.forecast.features import feature_row
from sr.forecast.publish import attach_t0
from sr.forecast.run import ArtifactMismatch, forecast_snapshot, load_models
from sr.marketdata.quote_rules import evaluate_quotes
from sr.snapshot.builder import Trigger, benchmark_version, build_snapshot
from sr.timeguard import LookaheadError
from sr.train import dataset as ds
from sr.train.train import run_training
from tests import test_move_models as tmm
from tests import test_train as ttr
from tests.test_dataset import PEERS_ALL, REFS, FrameProvider, synthetic_quotes

DAY = date(2026, 12, 10)
SLOT = et_to_utc(DAY, time(10, 0))  # sched-0.1 s1000
NVDA = "sec_nvda"


@pytest.fixture(scope="module")
def provider() -> FrameProvider:
    return FrameProvider(synthetic_quotes([NVDA, *PEERS_ALL, *REFS], seed=21))


def history(n_days: int = 6, end_before: datetime = SLOT) -> pd.DataFrame:
    """Realised windows of earlier sessions, every 5 minutes (synthetic) — enough for sigma-0.1."""
    rng = np.random.default_rng(1)
    rows = []
    from sr.calendar import get_calendar

    cal = get_calendar()
    s = cal.previous_open_session(DAY)
    sessions = []
    for _ in range(n_days):
        sessions.append(s)
        s = cal.previous_open_session(s.session_date)
    for s in sessions:
        assert s.open_at is not None
        for i in range(66):
            t0 = s.open_at + timedelta(minutes=5 * i, seconds=5)
            rows.append(
                {
                    "security_id": NVDA,
                    "session_date": s.session_date,
                    "t0_ts": pd.Timestamp(t0),
                    "end_ts": pd.Timestamp(t0 + timedelta(minutes=60)),
                    "relative_return_pp": float(rng.normal(0, 0.6)),
                }
            )
    return pd.DataFrame(
        rows, columns=["security_id", "session_date", "t0_ts", "end_ts", "relative_return_pp"]
    )


def models(conn, tmp_path: Path) -> Any:  # type: ignore[no-untyped-def]
    days = [s.session_date for s in ttr.CAL.open_sessions(ttr.START, ttr.END)]
    f, _ = ds.assign_splits(ttr.synthetic_frame(), days)
    d1 = ds.build_dataset(
        conn, None, [NVDA], ttr.START, ttr.END, out_dir=tmp_path, rows=f.drop(columns=["split"])
    )
    r1 = run_training(conn, d1.dataset_version_id, seed=1, out_dir=tmp_path)
    mf = tmm.move_frame()
    d2 = ds.build_dataset(
        conn,
        None,
        [NVDA],
        tmm.START,
        tmm.END,
        target_id="regular_60m_move",
        out_dir=tmp_path,
        rows=mf.drop(columns=["split"]),
    )
    r2 = run_training(conn, d2.dataset_version_id, seed=1, out_dir=tmp_path)
    return load_models(
        conn, r1.artifact_paths["model_version_id"], r2.artifact_paths["move_quantile_model_version_id"]
    )


def snapshot(conn, provider: FrameProvider, as_of: datetime, trigger: Trigger | None = None) -> str:  # type: ignore[no-untyped-def]
    conn.execute(
        """insert into collection_runs (collection_run_id, security_id, window_from, window_to, counts, started_at)
           values (%s, 'sec_nvda', %s, %s, '{}', %s) on conflict do nothing""",
        (f"cr_{as_of:%H%M%S%f}", as_of - timedelta(hours=1), as_of - timedelta(seconds=30), as_of),
    )
    _, w = benchmark_version(conn, NVDA, DAY)
    q = evaluate_quotes(provider.quotes_1s([NVDA, *w], as_of - timedelta(minutes=25), as_of))
    q = q[
        (q["received_at"] <= pd.Timestamp(as_of)) & (q["ts"] >= pd.Timestamp(as_of - timedelta(seconds=60)))
    ].reset_index(drop=True)
    prev = q.sort_values("ts").groupby("security_id")["mid"].first().to_dict()  # synthetic previous close
    r = build_snapshot(
        conn,
        NVDA,
        trigger or Trigger("scheduled", "sched_5m", as_of),
        q,
        prev,
        as_of + timedelta(milliseconds=300),
    )
    return r.snapshot_id


def evaluated(provider: FrameProvider, conn, start: datetime, end: datetime) -> pd.DataFrame:  # type: ignore[no-untyped-def]
    _, w = benchmark_version(conn, NVDA, DAY)
    q = evaluate_quotes(provider.quotes_1s([NVDA, *w], start - timedelta(minutes=25), end))
    return q[q["received_at"] <= pd.Timestamp(end)].reset_index(drop=True)


# ---------------------------------------------------------------- AC-13 / AC-27
def test_slot_forecast_publishes_both_targets(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    m = models(conn, tmp_path)
    snap = snapshot(conn, provider, SLOT)
    pub = SLOT + timedelta(milliseconds=600)
    res = forecast_snapshot(conn, snap, provider, m, history(), pub, feature_dir=tmp_path)
    assert not res.published.reused and len(res.published.run_ids) == 2
    rows = {r["target_row_id"]: dict(r) for r in conn.execute("select * from predictions").fetchall()}
    d, mv = rows["tgt_regular_60m_v1"], rows["tgt_regular_60m_move_v1"]
    # direction
    assert d["status"] == "published" and abs(sum(d["probabilities"].values()) - 1) < 1e-6
    assert d["predicted_class"] == max(d["probabilities"], key=d["probabilities"].get)
    assert float(d["threshold_pp"]) == pytest.approx(0.25 * float(d["sigma_hat_pp"]), abs=1e-9)
    assert d["sampling_rule"] == "schedule_slot" and d["is_primary"] and d["schedule_slot_id"] == "s1000"
    assert d["scheduled_for"] == SLOT and d["display_tier"] == "internal_shadow"  # candidate model
    for k in (
        "target_definition_version",
        "quote_rule_version",
        "benchmark_version_id",
        "calendar_version",
        "model_version_id",
        "calibration_version",
        "schema_version",
    ):  # AC-13: the version fields are set
        assert d["locked"][k], k
    assert d["locked"]["schema_version"] == "contract-0.7.3"
    base = np.asarray([m.class_frequency[c] for c in ("outperform", "flat", "underperform")])
    p = np.asarray([d["probabilities"][c] for c in ("outperform", "flat", "underperform")])
    assert float(d["edge_vs_baseline"]) == pytest.approx(float(((p - base) ** 2).sum()), abs=1e-5)
    # expected move (AC-27): same snapshot, published with it
    q = mv["move_quantiles"]
    assert (
        mv["status"] == "published"
        and q["unit"] == "abs_relative_pp"
        and 0 <= q["p50"] <= q["p80"] <= q["p90"]
    )
    assert (
        mv["probabilities"] is None
        and mv["locked"]["sigma_hat_pp"] is None
        and "threshold_pp" in mv["locked"]
    )
    runs = conn.execute("select * from prediction_runs").fetchall()
    assert {r["snapshot_id"] for r in runs} == {snap} and all(r["published_at"] == pub for r in runs)
    assert Path(runs[0]["feature_snapshot_id"]).exists()

    # t0: the first sync qualifying quote after publish, the same quote for both targets (AC-27)
    _, w = benchmark_version(conn, NVDA, DAY)
    q1 = evaluated(provider, conn, SLOT, SLOT + timedelta(minutes=2))
    t = [attach_t0(conn, r["prediction_id"], q1, w, SLOT + timedelta(minutes=2)) for r in rows.values()]
    assert {x.status for x in t} == {"attached"} and len({x.t0_quote_id for x in t}) == 1
    after = conn.execute(
        "select p.*, q.quote_ts from predictions p join reference_quotes q on q.quote_id = p.t0_quote_id"
    ).fetchall()
    for r in after:
        assert r["published_at"] < r["quote_ts"]  # AC-13
        assert r["status"] == "awaiting_settlement" and r["target_end_at"] == r["valid_until"]
        assert len(r["t0_benchmark_quote_ids"]) >= 10

    # AC-13: published forecast fields are frozen by the database
    with pytest.raises(psycopg.errors.RaiseException, match="IMMUTABLE"):
        with conn.transaction():
            conn.execute(
                "update predictions set probabilities = %s where prediction_id = %s",
                (json.dumps({"outperform": 1.0, "flat": 0.0, "underperform": 0.0}), d["prediction_id"]),
            )
    with pytest.raises(psycopg.errors.RaiseException, match="IMMUTABLE"):
        with conn.transaction():
            conn.execute(
                "update predictions set move_quantiles = '{}' where prediction_id = %s",
                (mv["prediction_id"],),
            )
    with pytest.raises(psycopg.errors.RaiseException, match="IMMUTABLE"):
        with conn.transaction():
            conn.execute("delete from predictions where prediction_id = %s", (d["prediction_id"],))

    # idempotent: the same snapshot + target + model returns the rows already published
    again = forecast_snapshot(conn, snap, provider, m, history(), pub, feature_dir=tmp_path)
    assert (
        again.published.reused and conn.execute("select count(*) as n from predictions").fetchone()["n"] == 2
    )


def test_abstentions(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    m = models(conn, tmp_path)
    # no sigma history -> direction abstains insufficient_data; the move target still forecasts
    snap = snapshot(conn, provider, SLOT)
    forecast_snapshot(conn, snap, provider, m, history(0), SLOT + timedelta(seconds=1), feature_dir=tmp_path)
    got = {
        r["target_row_id"]: r
        for r in conn.execute(
            "select * from predictions where run_id in (select run_id from prediction_runs where snapshot_id = %s)",
            (snap,),
        ).fetchall()
    }
    assert (
        got["tgt_regular_60m_v1"]["status"] == "abstained"
        and got["tgt_regular_60m_v1"]["abstain_reason"] == "insufficient_data"
    )
    assert (
        got["tgt_regular_60m_v1"]["probabilities"] is None
        and got["tgt_regular_60m_move_v1"]["status"] == "published"
    )
    # a slot published more than 180 s late -> slot_missed (sched-0.1 miss rule)
    snap2 = snapshot(conn, provider, et_to_utc(DAY, time(11, 30)))
    forecast_snapshot(conn, snap2, provider, m, history(), et_to_utc(DAY, time(11, 34)), feature_dir=tmp_path)
    reasons = {
        r["abstain_reason"]
        for r in conn.execute(
            "select p.* from predictions p join prediction_runs r using (run_id) where r.snapshot_id = %s",
            (snap2,),
        ).fetchall()
    }
    assert reasons == {"slot_missed"}
    # 15:20 ET: the 60-minute window no longer fits before the close (D-18)
    snap3 = snapshot(conn, provider, et_to_utc(DAY, time(15, 20)))
    forecast_snapshot(
        conn, snap3, provider, m, history(), et_to_utc(DAY, time(15, 20, 1)), feature_dir=tmp_path
    )
    r3 = conn.execute(
        "select p.* from predictions p join prediction_runs r using (run_id) where r.snapshot_id = %s",
        (snap3,),
    ).fetchall()
    assert {x["abstain_reason"] for x in r3} == {"window_insufficient"} and {
        x["sampling_rule"] for x in r3
    } == {"scheduled_5m"}
    assert not any(x["is_primary"] for x in r3)


def test_event_first_then_revision(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    m = models(conn, tmp_path)
    conn.execute(
        """insert into events (event_id, category, identity_key, first_seen_at)
                    values ('evt_demo', 'policy_export', 'policy:demo', %s)""",
        (SLOT,),
    )
    t1 = SLOT + timedelta(minutes=7)
    s1 = snapshot(conn, provider, t1, Trigger("event", "evt_demo", t1))
    forecast_snapshot(conn, s1, provider, m, history(), t1 + timedelta(seconds=1), feature_dir=tmp_path)
    t2 = SLOT + timedelta(minutes=12)
    s2 = snapshot(conn, provider, t2, Trigger("event", "evt_demo", t2))
    forecast_snapshot(conn, s2, provider, m, history(), t2 + timedelta(seconds=1), feature_dir=tmp_path)
    rows = conn.execute(
        "select * from predictions where target_row_id = 'tgt_regular_60m_v1' order by published_at"
    ).fetchall()
    assert [r["sampling_rule"] for r in rows] == ["event_first", "revision"]
    assert rows[0]["is_primary"] and not rows[1]["is_primary"]
    assert (
        rows[1]["supersedes_prediction_id"] == rows[0]["prediction_id"] and rows[0]["event_id"] == "evt_demo"
    )


def test_tampered_artifact_is_refused(conn, tmp_path) -> None:  # type: ignore[no-untyped-def]
    m = models(conn, tmp_path)
    row = conn.execute(
        "select * from model_versions where model_version_id = %s", (m.direction_id,)
    ).fetchone()
    Path(row["coefficients_path"]).write_text("{}")
    with pytest.raises(ArtifactMismatch):
        load_models(conn, m.direction_id, m.move_id)
    with pytest.raises(
        psycopg.errors.RaiseException, match="IMMUTABLE"
    ):  # a registered model cannot be edited
        with conn.transaction():
            conn.execute(
                "update model_versions set artifact_sha256 = 'x' where model_version_id = %s",
                (m.direction_id,),
            )
    conn.execute(
        "update model_versions set status = 'shadow' where model_version_id = %s", (m.direction_id,)
    )  # status may move


# ---------------------------------------------------------------- point in time (no DB)
def test_feature_row_refuses_future_series() -> None:
    t = SLOT
    s = pd.Series([1.0, 2.0], index=pd.DatetimeIndex([t - timedelta(minutes=1), t + timedelta(minutes=1)]))
    with pytest.raises(LookaheadError):
        feature_row({"NVDA": s}, NVDA, ["sec_amd"], t, DAY, 0.6, history())


def test_windows_ending_after_publish_are_ignored() -> None:
    from sr.forecast.features import realised_before

    h = history()
    late = pd.DataFrame(
        [
            {
                "security_id": NVDA,
                "session_date": DAY,
                "t0_ts": pd.Timestamp(SLOT - timedelta(minutes=30)),
                "end_ts": pd.Timestamp(SLOT + timedelta(minutes=30)),
                "relative_return_pp": 99.0,
            }
        ]
    )
    got = realised_before(pd.concat([h, late], ignore_index=True), SLOT)
    assert len(got) == len(h) and 99.0 not in set(got["relative_return_pp"])
    assert UTC  # noqa: B018  (timezone-aware fixtures)
