"""AC-29 (P0 part): fs-0.2 feature functions give determined values on the synthetic fixture and only read
ts <= as_of (anything later raises LookaheadError)."""

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from sr.config import load
from sr.features.calendar_feats import calendar_features, is_triple_witching
from sr.features.cross_asset import cross_asset_features
from sr.features.lead_lag import lead_lag_features
from sr.features.vol_regime import opening_range_pct, overnight_gap_pct, realized_vol_pct, vol_regime_features
from sr.timeguard import LookaheadError
from tests.conftest import PEERS_EX_NVDA, et

D = date(2026, 12, 1)
AS_OF = et(D, "11:30")


@pytest.fixture(scope="module")
def mids(raw_quotes: pd.DataFrame) -> dict[str, pd.Series]:
    """1-minute last NBBO mid per symbol, truncated at AS_OF (callers must slice; the functions verify)."""
    q = raw_quotes.assign(mid=(raw_quotes["bid"] + raw_quotes["ask"]) / 2)
    out = {}
    for sym, g in q.groupby("symbol"):
        s = g.set_index("ts")["mid"].resample("1min", label="right", closed="right").last()
        out[str(sym)] = s.loc[: pd.Timestamp(AS_OF)]
    return out


def test_feature_set_config() -> None:
    cfg = load("features/fs-0.2")
    assert cfg["feature_set_version"] == "fs-0.2"
    assert set(cfg["groups"]) == {"calendar", "cross_asset", "lead_lag", "vol_regime"}


def test_calendar_features() -> None:
    f = calendar_features(AS_OF)
    assert f == {
        "minutes_since_open": 120.0,
        "minutes_to_close": 270.0,
        "day_of_week": 1,
        "is_half_day": False,
        "is_triple_witching": False,
        "is_index_rebalance_day": False,
    }
    h = calendar_features(et(date(2026, 11, 27), "12:00"))
    assert h["is_half_day"] and h["minutes_to_close"] == 60.0
    pre = calendar_features(et(D, "08:30"))
    assert pre["minutes_since_open"] is None and pre["minutes_to_close"] is None
    assert is_triple_witching(date(2026, 12, 18)) and not is_triple_witching(date(2026, 12, 11))


def test_cross_asset_values_and_hand_check(mids: dict[str, pd.Series]) -> None:
    f = cross_asset_features(mids, AS_OF)
    assert set(f) == {
        "qqq_ret_30m",
        "qqq_ret_60m",
        "spy_ret_30m",
        "spy_ret_60m",
        "vix_level",
        "vix_change_30m",
    }
    assert all(v is not None and math.isfinite(v) for v in f.values())
    q = mids["QQQ"]
    hand = (q.loc[: pd.Timestamp(AS_OF)].iloc[-1] / q.loc[: pd.Timestamp(et(D, "11:00"))].iloc[-1] - 1) * 100
    assert f["qqq_ret_30m"] == pytest.approx(hand, abs=1e-12)
    assert f == cross_asset_features(mids, AS_OF)  # deterministic


def test_lead_lag(mids: dict[str, pd.Series]) -> None:
    f = lead_lag_features(mids, PEERS_EX_NVDA, AS_OF)
    assert len(f) == (len(PEERS_EX_NVDA) + 1) * 3 and "smh_ret_30m" in f and "amd_ret_5m" in f
    assert all(v is not None for v in f.values())


def test_vol_regime(mids: dict[str, pd.Series]) -> None:
    f = vol_regime_features(mids["NVDA"], AS_OF)
    assert f["rv_5m"] is not None and f["rv_30m"] is not None and f["rv_30m"] > 0
    assert f["rv_390m"] is None  # fixture has only 120 regular minutes before 11:30
    assert f["overnight_gap_pct"] is None  # no previous session in the one-day fixture
    assert f["opening_range_pct"] is not None and f["opening_range_pct"] > 0
    s = mids["NVDA"].dropna()
    r = np.diff(np.log(s.to_numpy()[-31:]))
    assert f["rv_30m"] == pytest.approx(math.sqrt(float(np.sum(r**2))) * 100, abs=1e-12)


def test_opening_range_needs_complete_range(mids: dict[str, pd.Series]) -> None:
    early = et(D, "09:50")
    assert opening_range_pct(mids["NVDA"].loc[: pd.Timestamp(early)], early) is None


def test_overnight_gap_two_sessions() -> None:
    idx = pd.DatetimeIndex(
        [
            pd.Timestamp(et(date(2026, 11, 30), "15:59")),
            pd.Timestamp(et(date(2026, 11, 30), "16:00")),
            pd.Timestamp(et(D, "09:31")),
            pd.Timestamp(et(D, "09:32")),
        ]
    )
    s = pd.Series([100.0, 100.0, 102.0, 103.0], index=idx)
    assert overnight_gap_pct(s, et(D, "09:32")) == pytest.approx(2.0)


# ---------------- point-in-time negative tests ----------------
@pytest.fixture(scope="module")
def full_day(raw_quotes: pd.DataFrame) -> dict[str, pd.Series]:
    q = raw_quotes.assign(mid=(raw_quotes["bid"] + raw_quotes["ask"]) / 2)
    return {str(s): g.set_index("ts")["mid"].resample("1min").last() for s, g in q.groupby("symbol")}


def test_features_raise_on_future_data(full_day: dict[str, pd.Series]) -> None:
    with pytest.raises(LookaheadError):
        cross_asset_features(full_day, AS_OF)
    with pytest.raises(LookaheadError):
        lead_lag_features(full_day, PEERS_EX_NVDA, AS_OF)
    with pytest.raises(LookaheadError):
        realized_vol_pct(full_day["NVDA"], AS_OF, 30)
    with pytest.raises(LookaheadError):
        vol_regime_features(full_day["NVDA"], AS_OF)


def test_one_future_point_is_enough_to_fail(mids: dict[str, pd.Series]) -> None:
    s = mids["NVDA"].copy()
    s.loc[pd.Timestamp(AS_OF) + pd.Timedelta(seconds=1)] = 1.0
    with pytest.raises(LookaheadError):
        realized_vol_pct(s, AS_OF, 5)
