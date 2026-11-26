"""AC-04 (part 1): qr-0.1 qualifying-quote rules on unit frames and on the synthetic fixture."""

from datetime import date

import pandas as pd
import pytest

from sr.marketdata.quote_rules import QuoteRules, evaluate_quotes
from tests.conftest import et

D = date(2026, 12, 1)
T0 = pd.Timestamp("2026-12-01T15:00:00Z")


def frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    base = {"security_id": "sec_x", "halted": False, "luld_pause": False}
    out = []
    for i, r in enumerate(rows):
        ts = T0 + pd.Timedelta(seconds=i)
        age = float(r.pop("age", 0.2))  # type: ignore[arg-type]
        q = ts - pd.Timedelta(seconds=age)
        out.append(base | {"ts": ts, "quote_ts": q, "received_at": q + pd.Timedelta(milliseconds=100)} | r)
    return pd.DataFrame(out)


def mid_spread(mid: float, bp: float) -> dict[str, float]:
    h = mid * bp / 2e4
    return {"bid": mid - h, "ask": mid + h}


def test_rules_loaded_from_config() -> None:
    r = QuoteRules.from_config()
    assert (r.version, r.max_spread_bp, r.max_spread_vs_median_mult, r.max_quote_age_s) == (
        "qr-0.1",
        20,
        5,
        5,
    )


def test_spread_boundary_20bp() -> None:
    ev = evaluate_quotes(frame([mid_spread(100, 19.999), mid_spread(100, 20.001)]))
    assert ev["is_qualifying"].tolist() == [True, False]
    assert ev.loc[1, "quality_flags"] == ["wide_spread"]


def test_spread_vs_rolling_median() -> None:
    rows = [mid_spread(100, 2.0) for _ in range(30)] + [mid_spread(100, 12.0)]  # 12bp > 5 x ~2bp median
    ev = evaluate_quotes(frame(rows))
    assert ev["is_qualifying"].iloc[:30].all()
    assert not ev["is_qualifying"].iloc[30] and "wide_spread" in ev["quality_flags"].iloc[30]


def test_quote_age_boundary() -> None:
    ev = evaluate_quotes(frame([mid_spread(100, 2) | {"age": 5.0}, mid_spread(100, 2) | {"age": 5.001}]))
    assert ev["is_qualifying"].tolist() == [True, False]
    assert ev.loc[1, "quality_flags"] == ["stale"]


@pytest.mark.parametrize(
    "row,flag",
    [
        ({"bid": 100.0, "ask": 100.0}, "crossed"),
        ({"bid": 100.1, "ask": 100.0}, "crossed"),
        ({"bid": 0.0, "ask": 100.0}, None),
        (mid_spread(100, 2) | {"halted": True}, "halted"),
        (mid_spread(100, 2) | {"luld_pause": True}, "luld_pause"),
    ],
)
def test_book_and_status_rules(row: dict[str, object], flag: str | None) -> None:
    ev = evaluate_quotes(frame([row]))
    assert not ev.loc[0, "is_qualifying"]
    if flag:
        assert flag in ev.loc[0, "quality_flags"]


def test_delayed_is_flagged_but_still_qualifying() -> None:
    f = frame([mid_spread(100, 2)])
    f.loc[0, "received_at"] = f.loc[0, "quote_ts"] + pd.Timedelta(seconds=6)
    ev = evaluate_quotes(f)
    assert ev.loc[0, "quality_flags"] == ["delayed"] and ev.loc[0, "is_qualifying"]


def test_no_last_trade_fallback() -> None:
    with pytest.raises(ValueError):
        QuoteRules.from_config(
            {**__import__("sr.config", fromlist=["load"]).load("quote_rules"), "fallback_to_last_trade": True}
        )


# ---------------- fixture anomalies (synthetic) ----------------
def rows_at(ev: pd.DataFrame, sec: str, hhmmss: str) -> pd.Series:
    t = pd.Timestamp(et(D, hhmmss))
    r = ev[(ev["security_id"] == sec) & (ev["ts"] == t)]
    assert len(r) == 1
    return r.iloc[0]


def test_fixture_wide_spread_segment(evaluated: pd.DataFrame) -> None:
    r = rows_at(evaluated, "sec_nvda", "11:01:00")
    assert not r["is_qualifying"] and "wide_spread" in r["quality_flags"]
    assert rows_at(evaluated, "sec_nvda", "11:03:00")["is_qualifying"]


def test_fixture_halt_segment(evaluated: pd.DataFrame) -> None:
    for t in ("13:15:00", "13:16:30", "13:17:59"):
        r = rows_at(evaluated, "sec_nvda", t)
        assert not r["is_qualifying"] and "halted" in r["quality_flags"]
    seg = evaluated[(evaluated["security_id"] == "sec_nvda") & (evaluated["halted"])]
    assert len(seg) == 180  # exactly 3 minutes


def test_fixture_stale_quote(evaluated: pd.DataFrame) -> None:
    r = rows_at(evaluated, "sec_intc", "10:20:25")
    assert r["age_s"] > 5 and "stale" in r["quality_flags"] and not r["is_qualifying"]


def test_fixture_is_marked_synthetic(fixture_path) -> None:  # type: ignore[no-untyped-def]
    from sr.marketdata.providers.fixture import FixtureProvider

    p = FixtureProvider(fixture_path)
    assert p.synthetic and "SYNTHETIC" in p.metadata["label"]
