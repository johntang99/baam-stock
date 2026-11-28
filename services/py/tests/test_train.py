"""DP 1.12 first training run: baselines, market_logit, calibration, metrics (AC-16; D-24, D-30; OQ-46). SYNTHETIC."""

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sr.calendar import get_calendar
from sr.labels.thresholds import classify
from sr.train import dataset as ds
from sr.train.calibrate import Calibrator
from sr.train.train import (
    AvailabilityError,
    MarketLogit,
    persistence_labels,
    run_training,
    train_and_evaluate,
)

CAL = get_calendar()
START, END = date(2026, 12, 1), date(2027, 2, 26)
FEATS = [
    "minutes_since_open",
    "minutes_to_close",
    "qqq_ret_30m",
    "qqq_ret_60m",
    "spy_ret_30m",
    "spy_ret_60m",
    "vix_level",
    "vix_change_30m",
    "smh_ret_5m",
    "smh_ret_15m",
    "smh_ret_30m",
    "rv_5m",
    "rv_30m",
    "rv_390m",
    "overnight_gap_pct",
    "opening_range_pct",
]


def synthetic_frame(
    seed: int = 3, per_day: int = 24, signal: float = 0.6, start: date = START, end: date = END
) -> pd.DataFrame:
    """Dataset-shaped rows; relative return depends on qqq_ret_30m (synthetic, NOT market data)."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in CAL.open_sessions(start, end):
        assert s.open_at is not None
        for i in range(per_day):
            t = s.open_at + timedelta(minutes=5 * i)
            f = {f"f_{n}": float(rng.normal()) for n in FEATS}
            f |= {f"f_{p}_ret_{h}m": float(rng.normal()) for p in ("amd", "mu") for h in (5, 15, 30)}
            f["f_vix_level"] = None if i == 3 else f["f_vix_level"]  # some missing inputs
            rel = signal * f["f_qqq_ret_30m"] + float(rng.normal(0, 0.6))
            sigma = 0.6
            rows.append(
                {
                    "security_id": "sec_nvda",
                    "session_date": s.session_date,
                    "sample_ts": pd.Timestamp(t),
                    "t0_ts": pd.Timestamp(t + timedelta(seconds=5)),
                    "t0_quote_ts": pd.Timestamp(t + timedelta(seconds=5)),
                    "end_ts": pd.Timestamp(t + timedelta(minutes=60, seconds=5)),
                    "relative_return_pp": rel,
                    "sigma_hat_pp": sigma,
                    "threshold_pp": 0.25 * sigma,
                    "label": classify(rel, 0.25 * sigma),
                    "benchmark_version_id": "bmv_semis_peer_ex_nvda_v1",
                    "event_cluster": None,
                    "exclusion": None,
                    **f,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    days = [s.session_date for s in CAL.open_sessions(START, END)]
    f, _ = ds.assign_splits(synthetic_frame(), days)
    return f


@pytest.fixture(scope="module")
def trained(frame: pd.DataFrame):  # type: ignore[no-untyped-def]
    return train_and_evaluate(frame, seed=11)


def _m(out, subset: str, metric: str, ref: str | None = None, group: str = "all"):  # type: ignore[no-untyped-def]
    return next(
        x
        for x in out.metrics
        if (x.subset, x.metric, x.reference_model, x.group_key) == (subset, metric, ref, group)
    )


# ---------------------------------------------------------------- pure training (no DB)
def test_ac16_metrics_per_subset(frame, trained) -> None:  # type: ignore[no-untyped-def]
    for subset in ("train", "calibration", "validation"):
        for metric in ("brier", "log_loss", "hit_rate", "coverage", "ece", "n_effective"):
            _m(trained, subset, metric)
        for ref in ("class_frequency", "always_flat", "persistence"):
            b = _m(trained, subset, "brier_skill_score", ref)
            assert b.ci95_low is not None and b.ci95_high is not None and b.ci95_low <= b.value <= b.ci95_high
        n_days = frame.loc[(frame["split"] == subset) & frame["exclusion"].isna(), "session_date"].nunique()
        assert _m(trained, subset, "n_effective").value == n_days  # counted in trading days
    assert _m(trained, "validation", "coverage").value == 1.0
    assert {x.group_key for x in trained.metrics} == {"all", "security:sec_nvda"}


def test_market_logit_beats_the_references_on_signal(trained) -> None:  # type: ignore[no-untyped-def]
    assert _m(trained, "validation", "brier_skill_score", "class_frequency").value > 0
    assert _m(trained, "validation", "brier_skill_score", "always_flat").value > 0
    assert _m(trained, "validation", "brier_skill_score", "persistence").value > 0


def test_no_signal_gives_no_skill() -> None:
    days = [s.session_date for s in CAL.open_sessions(START, END)]
    f, _ = ds.assign_splits(synthetic_frame(seed=5, signal=0.0), days)
    out = train_and_evaluate(f, seed=11)
    b = _m(out, "validation", "brier_skill_score", "class_frequency")
    assert b.ci95_low < 0.05  # cannot claim skill that is not there


def test_same_seed_same_metrics(frame, trained) -> None:  # type: ignore[no-untyped-def]
    again = train_and_evaluate(frame, seed=11)
    assert [
        (m.subset, m.metric, m.reference_model, m.value, m.ci95_low, m.ci95_high) for m in trained.metrics
    ] == [(m.subset, m.metric, m.reference_model, m.value, m.ci95_low, m.ci95_high) for m in again.metrics]


def test_model_round_trips_through_json(frame, trained) -> None:  # type: ignore[no-untyped-def]
    from sr.train.train import add_derived, design

    back = MarketLogit.from_dict(json.loads(json.dumps(trained.model.to_dict())))
    X = design(add_derived(frame.head(50)), back.features)
    np.testing.assert_allclose(back.proba(X), trained.model.proba(X))
    p = back.proba(X)
    assert np.allclose(p.sum(axis=1), 1.0) and (p >= 0).all() and len(back.features) == 20


def test_calibration_method_depends_on_size(trained) -> None:  # type: ignore[no-untyped-def]
    assert trained.model.calibrator is not None and trained.model.calibrator.method in ("isotonic", "platt")
    rng = np.random.default_rng(0)
    raw = rng.dirichlet([1, 1, 1], size=100)
    y = rng.integers(0, 3, size=100)
    assert Calibrator.fit(raw, y, isotonic_min_rows=300).method == "platt"
    big = Calibrator.fit(
        rng.dirichlet([1, 1, 1], size=400), rng.integers(0, 3, size=400), isotonic_min_rows=300
    )
    assert big.method == "isotonic"
    out = big.transform(raw)
    assert np.allclose(out.sum(axis=1), 1.0) and (out >= 0).all() and (out <= 1).all()


def test_two_class_train_split() -> None:
    days = [s.session_date for s in CAL.open_sessions(START, END)]
    f = synthetic_frame(seed=8)
    f["label"] = np.where(f["relative_return_pp"] > 0, "outperform", "underperform")
    f, _ = ds.assign_splits(f, days)
    out = train_and_evaluate(f, seed=1)
    from sr.train.train import add_derived, design

    p = out.model.raw_proba(design(add_derived(f.head(20)), out.model.features))
    assert np.allclose(p.sum(axis=1), 1.0) and (p[:, 1] < 1e-6).all()  # "flat" never seen -> ~0


def test_persistence_uses_only_ended_windows() -> None:
    t = pd.Timestamp("2026-12-01 15:00", tz="UTC")
    hist = pd.DataFrame(
        {
            "security_id": ["sec_nvda"] * 3,
            "end_ts": [t - pd.Timedelta(minutes=10), t, t + pd.Timedelta(minutes=1)],
            "relative_return_pp": [-1.0, 1.0, -5.0],
        }
    )
    rows = pd.DataFrame(
        {
            "security_id": ["sec_nvda"] * 3,
            "sample_ts": [t - pd.Timedelta(minutes=20), t - pd.Timedelta(minutes=5), t],
            "threshold_pp": [0.15, 0.15, 0.15],
        }
    )
    assert persistence_labels(rows, hist) == [None, "underperform", "outperform"]  # never the 15:01 window


# ---------------------------------------------------------------- AC-16 on the database
def _dataset(conn, frame: pd.DataFrame, tmp_path: Path, ok: bool = True) -> str:  # type: ignore[no-untyped-def]
    r = ds.build_dataset(
        conn, None, ["sec_nvda"], START, END, out_dir=tmp_path, rows=frame.drop(columns=["split"])
    )
    if not ok:
        conn.execute(
            "update training_dataset_versions set availability_check_passed = false where dataset_version_id = %s",
            (r.dataset_version_id,),
        )
    return r.dataset_version_id


def test_ac16_training_run_completed(conn, frame, tmp_path) -> None:  # type: ignore[no-untyped-def]
    ds_id = _dataset(conn, frame, tmp_path)
    res = run_training(conn, ds_id, seed=11, out_dir=tmp_path)
    run = conn.execute(
        "select * from training_runs where training_run_id = %s", (res.training_run_id,)
    ).fetchone()
    assert run["status"] == "completed" and run["finished_at"] is not None and run["random_seed"] == 11
    assert run["code_version"] and len(run["config_hash"]) == 64
    ms = conn.execute(
        "select * from training_run_metrics where training_run_id = %s", (res.training_run_id,)
    ).fetchall()
    got = {(m["subset"], m["metric"], m["reference_model"]) for m in ms if m["group_key"] == "all"}
    for subset in ("train", "calibration", "validation"):
        for ref in ("class_frequency", "always_flat", "persistence"):
            assert (subset, "brier_skill_score", ref) in got
        assert {(subset, x, None) for x in ("brier", "hit_rate", "coverage", "n_effective")} <= got
    assert all(m["ci95_low"] is not None for m in ms if m["metric"] == "brier_skill_score")
    art = Path(run["artifact_paths"]["market_logit"])
    import hashlib

    assert art.exists() and hashlib.sha256(art.read_bytes()).hexdigest() == run["artifact_paths"]["sha256"]
    assert run["artifact_paths"]["model_version_id"].startswith("mdl_")
    # the same dataset + config + seed + code: the existing run is returned, nothing is retrained
    again = run_training(conn, ds_id, seed=11, out_dir=tmp_path)
    assert again.reused and again.training_run_id == res.training_run_id
    assert [m.value for m in again.metrics] == pytest.approx([m.value for m in res.metrics])


def test_failed_availability_check_fails_the_run(conn, frame, tmp_path) -> None:  # type: ignore[no-untyped-def]
    ds_id = _dataset(conn, frame, tmp_path, ok=False)
    with pytest.raises(AvailabilityError):
        run_training(conn, ds_id, seed=11, out_dir=tmp_path)
    run = conn.execute("select * from training_runs where dataset_version_id = %s", (ds_id,)).fetchone()
    assert run["status"] == "failed" and run["error"]["code"] == "availability_check_failed"
    assert (
        conn.execute(
            "select count(*) as n from training_run_metrics where training_run_id = %s",
            (run["training_run_id"],),
        ).fetchone()["n"]
        == 0
    )


def test_row_with_future_t0_fails_the_run(conn, frame, tmp_path) -> None:  # type: ignore[no-untyped-def]
    bad = frame.copy()
    i = bad.index[bad["exclusion"].isna()][0]
    bad.loc[i, "t0_quote_ts"] = bad.loc[i, "sample_ts"]  # t0 not after the sample time
    ds_id = _dataset(conn, bad, tmp_path)
    with pytest.raises(AvailabilityError):
        run_training(conn, ds_id, seed=11, out_dir=tmp_path)
