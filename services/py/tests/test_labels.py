"""AC-26: sigma-0.1 + vol-scaled thresholds (D-09)."""

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from sr.calendar import get_calendar
from sr.labels.sigma import estimate_sigma
from sr.labels.thresholds import Abstain, LockedThreshold, classify, lock_threshold, threshold_pp
from sr.timeguard import LookaheadError
from tests.conftest import et

TARGET_DAY = date(2026, 12, 1)


def history(values: list[float], hhmm: str = "10:00", end_day: date = date(2026, 11, 30)) -> pd.DataFrame:
    """One settled 60m window per past session at hhmm ET, most recent session last."""
    cal = get_calendar()
    if not values:
        return pd.DataFrame(columns=["window_start", "window_end", "relative_return_pp"])
    sessions = [s.session_date for s in cal.open_sessions(end_day - timedelta(days=60), end_day)][
        -len(values) :
    ]
    rows = []
    for d, v in zip(sessions, values, strict=True):
        ws = pd.Timestamp(et(d, hhmm))
        rows.append(
            {"window_start": ws, "window_end": ws + pd.Timedelta(minutes=60), "relative_return_pp": v}
        )
    return pd.DataFrame(rows)


AS_OF = et(TARGET_DAY, "10:00")


def test_constant_magnitude_gives_sigma_060() -> None:
    h = history([0.6 if i % 2 else -0.6 for i in range(25)])
    est = estimate_sigma(h, et(TARGET_DAY, "10:00"), AS_OF)
    assert est.sigma_hat_pp == pytest.approx(0.60, abs=1e-12)
    assert est.n_obs == 20 and est.sigma_model_version == "sigma-0.1"  # only the last 20 sessions


def test_ewma_half_life_weighting_by_hand() -> None:
    # 10 obs of 1.0pp aged 11..20 sessions and 10 obs of 2.0pp aged 1..10 sessions
    h = history([1.0] * 10 + [2.0] * 10)
    est = estimate_sigma(h, et(TARGET_DAY, "10:00"), AS_OF)
    w = [0.5 ** (a / 10) for a in range(1, 21)]
    r2 = [4.0] * 10 + [1.0] * 10  # ages 1..10 -> 2.0pp, ages 11..20 -> 1.0pp
    assert est.sigma_hat_pp == pytest.approx(
        math.sqrt(sum(a * b for a, b in zip(w, r2, strict=True)) / sum(w)), abs=1e-12
    )


def test_only_same_time_bucket_is_used() -> None:
    h = pd.concat([history([0.6] * 20, "10:00"), history([9.0] * 20, "14:30")])
    assert estimate_sigma(h, et(TARGET_DAY, "10:05"), AS_OF).sigma_hat_pp == pytest.approx(0.6)


def test_insufficient_history_abstains() -> None:
    est = estimate_sigma(history([0.6] * 5), et(TARGET_DAY, "10:00"), AS_OF)
    assert est.sigma_hat_pp is None and est.reason == "insufficient_data"
    lt = lock_threshold(est.sigma_hat_pp)
    assert isinstance(lt, Abstain) and lt.abstain_reason == "insufficient_data"
    assert estimate_sigma(history([]), et(TARGET_DAY, "10:00"), AS_OF).reason == "insufficient_data"


def test_future_data_raises() -> None:
    h = history([0.6] * 20)
    future = pd.DataFrame(
        [
            {
                "window_start": pd.Timestamp(et(TARGET_DAY, "10:00")),
                "window_end": pd.Timestamp(et(TARGET_DAY, "11:00")),
                "relative_return_pp": 5.0,
            }
        ]
    )
    with pytest.raises(LookaheadError):
        estimate_sigma(pd.concat([h, future]), et(TARGET_DAY, "10:00"), AS_OF)


def test_threshold_and_classes_ac26() -> None:
    lt = lock_threshold(0.60)
    assert isinstance(lt, LockedThreshold)
    assert lt.threshold_pp == pytest.approx(0.15) and threshold_pp(0.60, 0.25) == 0.15
    assert classify(0.24, lt.threshold_pp) == "outperform"
    assert classify(0.15, lt.threshold_pp) == "flat"  # boundary is flat
    assert classify(-0.15, lt.threshold_pp) == "flat"
    assert classify(0.1500001, lt.threshold_pp) == "outperform"
    assert classify(-0.1500001, lt.threshold_pp) == "underperform"
    locked = lt.as_locked()
    assert set(locked) == {"sigma_hat_pp", "threshold_k", "threshold_pp", "sigma_model_version"}
    assert locked == {
        "sigma_model_version": "sigma-0.1",
        "sigma_hat_pp": 0.6,
        "threshold_k": 0.25,
        "threshold_pp": 0.15,
    }


@pytest.mark.parametrize("bad", [None, 0.0, float("nan")])
def test_missing_or_zero_sigma_abstains(bad: float | None) -> None:
    assert isinstance(lock_threshold(bad), Abstain)
