"""DP 1.13 expected-move models: HAR baseline + GBDT quantiles (D-29; AC-27 training part; OQ-47). SYNTHETIC."""

import hashlib
import pickle
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sr.eval.metrics import pinball_loss
from sr.train import dataset as ds
from sr.train.models.har_vol import HarVol, har_terms
from sr.train.move import pinball_rows, train_and_evaluate_move
from sr.train.train import run_training
from tests.test_train import CAL, synthetic_frame

# ~10 months so validation spans ~20 independent trading days (daily volatility regimes)
START, END = date(2026, 12, 1), date(2027, 9, 30)
DAYS = [s.session_date for s in CAL.open_sessions(START, END)]


def move_frame(seed: int = 4) -> pd.DataFrame:
    """|relative return| with persistent daily volatility regimes and a feature that scales it (synthetic)."""
    rng = np.random.default_rng(seed)
    f = synthetic_frame(seed=seed, per_day=8, start=START, end=END).drop(columns=["label", "threshold_pp"])
    vol = np.empty(len(DAYS))
    v = 0.0
    for i in range(len(DAYS)):  # AR(1) log-vol: yesterday's level predicts today's
        v = 0.85 * v + rng.normal(0, 0.35)
        vol[i] = 0.5 * np.exp(v)
    day_vol = dict(zip(DAYS, vol, strict=True))
    scale = f["session_date"].map(day_vol).to_numpy() * np.exp(0.3 * f["f_rv_30m"].to_numpy())
    f["relative_return_pp"] = rng.normal(0, 1, len(f)) * scale
    f["label_value"] = f["relative_return_pp"].abs()
    out, _ = ds.assign_splits(f, DAYS)
    return out


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    return move_frame()


@pytest.fixture(scope="module")
def trained(frame):  # type: ignore[no-untyped-def]
    return train_and_evaluate_move(frame, seed=5)


def _m(out, subset: str, metric: str, group: str = "all", ref: str | None = None):  # type: ignore[no-untyped-def]
    return next(
        x
        for x in out.metrics
        if (x.subset, x.metric, x.group_key, x.reference_model) == (subset, metric, group, ref)
    )


def test_pinball_rows_matches_scoring_function() -> None:
    q, y = np.asarray([0.2, 0.5, 1.0]), np.asarray([0.4, 0.5, 0.3])
    for tau in (0.5, 0.8, 0.9):
        assert np.allclose(
            pinball_rows(tau, q, y), [pinball_loss(tau, a, b) for a, b in zip(q, y, strict=True)]
        )


def test_har_terms_use_earlier_sessions_only() -> None:
    d = DAYS[:4]
    hist = pd.DataFrame(
        {
            "security_id": "sec_nvda",
            "session_date": [d[0], d[0], d[1], d[2]],
            "relative_return_pp": [1.0, -3.0, 4.0, 6.0],
        }
    )
    rows = pd.DataFrame({"security_id": "sec_nvda", "session_date": [d[0], d[2], d[3]]})
    t = har_terms(rows, hist)
    assert np.isnan(t.loc[0, "har_rv_d"])  # nothing before the first day
    assert t.loc[1, "har_rv_d"] == 4.0 and t.loc[1, "har_rv_w"] == pytest.approx((1 + 3 + 4) / 3)
    assert t.loc[2, "har_rv_d"] == 6.0
    # changing the row's own day never changes its terms (no same-day leakage)
    hist2 = hist.copy()
    hist2.loc[hist2["session_date"] == d[2], "relative_return_pp"] = 100.0
    assert har_terms(rows.iloc[[1]], hist2)["har_rv_d"].iloc[0] == 4.0


def test_ac27_training_metrics(trained) -> None:  # type: ignore[no-untyped-def]
    for subset in ("train", "calibration", "validation"):
        _m(trained, subset, "pinball_loss")
        _m(trained, subset, "pinball_loss", "har_vol:all")
        cmp_ = _m(trained, subset, "pinball_loss", "all", "har_vol")  # model − HAR with a day-block CI
        assert cmp_.ci95_low is not None and cmp_.ci95_low <= cmp_.value <= cmp_.ci95_high
        for q in ("p50", "p80", "p90"):
            _m(trained, subset, "interval_coverage", f"all|{q}")
            _m(trained, subset, "interval_width", f"all|{q}")
            _m(trained, subset, "interval_coverage", f"har_vol:all|{q}")


def test_conformal_calibration_hits_nominal_coverage(trained) -> None:  # type: ignore[no-untyped-def]
    for q, nominal in (("p50", 0.5), ("p80", 0.8), ("p90", 0.9)):
        assert _m(trained, "calibration", "interval_coverage", f"all|{q}").value == pytest.approx(
            nominal, abs=0.02
        )
        assert _m(trained, "calibration", "interval_coverage", f"har_vol:all|{q}").value == pytest.approx(
            nominal, abs=0.02
        )
        assert abs(_m(trained, "validation", "interval_coverage", f"all|{q}").value - nominal) < 0.12


def test_har_captures_persistent_volatility(frame, trained) -> None:  # type: ignore[no-untyped-def]
    """Out of sample on an independent ~210-day synthetic history: HAR beats a constant quantile. (A single
    20-day split can sit in a calm stretch where nothing beats a constant — the reason MP §12 asks for >= 60 days.)"""
    other = move_frame(seed=99)
    test = har_terms(other, other)
    test = test[test["har_rv_d"].notna()]
    y = test["label_value"].to_numpy()
    tr = frame[frame["split"] == "train"]["label_value"]
    lv = {"p50": 0.5, "p80": 0.8, "p90": 0.9}
    const = {q: np.full(len(y), float(np.quantile(tr, p))) for q, p in lv.items()}
    har_q = trained.har.quantiles(test)
    const_loss = np.mean([pinball_rows(lv[q], const[q], y).mean() for q in lv])
    har_loss = np.mean([pinball_rows(lv[q], har_q[q], y).mean() for q in lv])
    assert har_loss < const_loss  # yesterday's volatility predicts today's
    assert trained.har.coef[1] > 0  # RV_d enters with a positive weight


def test_quantiles_ordered_and_non_negative(frame, trained) -> None:  # type: ignore[no-untyped-def]
    rows = har_terms(frame.head(200), frame)
    from sr.train.train import add_derived

    q = trained.model.predict(add_derived(rows))
    assert (q["p50"] <= q["p80"]).all() and (q["p80"] <= q["p90"]).all() and (q["p50"] >= 0).all()


def test_same_seed_same_metrics(frame, trained) -> None:  # type: ignore[no-untyped-def]
    again = train_and_evaluate_move(frame, seed=5)
    assert [(m.subset, m.group_key, m.metric, m.value) for m in trained.metrics] == [
        (m.subset, m.group_key, m.metric, m.value) for m in again.metrics
    ]


def test_har_round_trips_through_json(frame, trained) -> None:  # type: ignore[no-untyped-def]
    import json

    back = HarVol.from_dict(json.loads(json.dumps(trained.har.to_dict())))
    rows = har_terms(frame.head(30), frame)
    for q in ("p50", "p80", "p90"):
        np.testing.assert_allclose(back.quantiles(rows)[q], trained.har.quantiles(rows)[q])


def test_move_training_run_on_the_database(conn, frame, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    r = ds.build_dataset(
        conn,
        None,
        ["sec_nvda"],
        START,
        END,
        target_id="regular_60m_move",
        out_dir=tmp_path,
        rows=frame.drop(columns=["split"]),
    )
    res = run_training(conn, r.dataset_version_id, seed=5, out_dir=tmp_path)
    run = conn.execute(
        "select * from training_runs where training_run_id = %s", (res.training_run_id,)
    ).fetchone()
    assert run["status"] == "completed"
    ap = run["artifact_paths"]
    for k in ("har_vol", "move_quantile"):
        p = Path(ap[k])
        assert p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == ap[f"{k}_sha256"]
        assert ap[f"{k}_model_version_id"].startswith("mdl_")
    model = pickle.loads(Path(ap["move_quantile"]).read_bytes())["model"]
    assert set(model.quantiles) == {"p50", "p80", "p90"}
    ms = conn.execute(
        "select * from training_run_metrics where training_run_id = %s", (res.training_run_id,)
    ).fetchall()
    assert any(
        m["metric"] == "pinball_loss" and m["reference_model"] == "har_vol" and m["ci95_low"] is not None
        for m in ms
    )
    assert {m["target_id"] for m in ms} == {"regular_60m_move"}
    assert any(m["metric"] == "interval_coverage" and m["group_key"] == "all|p80" for m in ms)
