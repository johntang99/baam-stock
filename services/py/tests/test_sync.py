"""AC-04 (part 2): first synchronous qualifying quote after publish (D-06, D-07; DC §4)."""

from datetime import date

import pandas as pd
import pytest

from sr.marketdata.quote_rules import evaluate_quotes
from sr.marketdata.sync import find_first_sync_qualifying
from sr.timeguard import LookaheadError
from tests.conftest import et

D = date(2026, 12, 1)


def sync(evaluated: pd.DataFrame, basket: list[str], hhmmss: str, **kw):  # type: ignore[no-untyped-def]
    return find_first_sync_qualifying(et(D, hhmmss), "sec_nvda", basket, 2000, 30, quotes=evaluated, **kw)


def test_normal_sync_after_publish(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    pub = pd.Timestamp(et(D, "10:00:00"))
    r = sync(evaluated, basket_ex_nvda, "10:00:00")
    assert r.status == "ok"
    assert r.quote is not None and r.quote["quote_ts"] > pub  # published_at < t0 quote_ts
    assert pub < r.sample_ts <= pub + pd.Timedelta(seconds=30)  # type: ignore[operator]
    assert len(r.constituent_quotes) >= 10  # stock + >= 10 constituents
    for c in r.constituent_quotes.values():
        assert abs(c["quote_ts"] - r.quote["quote_ts"]) <= pd.Timedelta(seconds=2)  # type: ignore[operator]


def test_halt_no_sync_within_30s(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    r = sync(evaluated, basket_ex_nvda, "13:15:30")
    assert r.status == "no_sync" and r.invalid_reason == "no_sync_start_quote"


def test_two_constituents_missing_no_sync(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    r = sync(evaluated, basket_ex_nvda, "14:40:10")  # AMD + MU in LULD pause
    assert r.status == "no_sync" and r.invalid_reason == "no_sync_start_quote"


def test_one_constituent_missing_still_syncs(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    r = sync(evaluated, basket_ex_nvda, "10:20:20")  # INTC stale
    assert r.status == "ok" and r.missing_constituents == ("sec_intc",)


def test_wide_spread_window_no_sync(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    assert sync(evaluated, basket_ex_nvda, "11:00:10").status == "no_sync"
    assert sync(evaluated, basket_ex_nvda, "11:01:50").status == "ok"  # spread normal from 11:02:00


def test_settlement_end_uses_inclusive_window(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    r = find_first_sync_qualifying(
        et(D, "11:20:03"),
        "sec_nvda",
        basket_ex_nvda,
        2000,
        30,
        quotes=evaluated,
        inclusive=True,
        invalid_reason_if_none="no_sync_end_quote",
    )
    assert r.status == "ok" and r.quote["quote_ts"] >= pd.Timestamp(et(D, "11:20:03"))  # type: ignore[index]


def test_end_quote_reason(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    r = find_first_sync_qualifying(
        et(D, "13:16:00"),
        "sec_nvda",
        basket_ex_nvda,
        2000,
        30,
        quotes=evaluated,
        inclusive=True,
        invalid_reason_if_none="no_sync_end_quote",
    )
    assert r.status == "no_sync" and r.invalid_reason == "no_sync_end_quote"


def test_lookahead_window_not_finished(evaluated: pd.DataFrame, basket_ex_nvda: list[str]) -> None:
    with pytest.raises(LookaheadError):
        sync(evaluated, basket_ex_nvda, "10:00:00", as_of=et(D, "10:00:10"))


def test_quotes_received_after_as_of_are_invisible() -> None:
    base = pd.Timestamp("2026-12-01T15:00:00Z")
    rows = []
    for sec in ["sec_t", "sec_a", "sec_b"]:
        for i in range(1, 6):
            ts = base + pd.Timedelta(seconds=i)
            late = sec == "sec_a"  # constituent A's quotes arrive 60s late
            rows.append(
                {
                    "ts": ts,
                    "security_id": sec,
                    "quote_ts": ts - pd.Timedelta(milliseconds=100),
                    "received_at": ts + pd.Timedelta(seconds=60 if late else 0.1),
                    "bid": 99.99,
                    "ask": 100.01,
                    "halted": False,
                    "luld_pause": False,
                }
            )
    ev = evaluate_quotes(pd.DataFrame(rows))
    kw = dict(quotes=ev, max_missing=0)
    assert find_first_sync_qualifying(base, "sec_t", ["sec_a", "sec_b"], 2000, 5, **kw).status == "ok"
    r = find_first_sync_qualifying(
        base, "sec_t", ["sec_a", "sec_b"], 2000, 5, as_of=base + pd.Timedelta(seconds=10), **kw
    )
    assert r.status == "no_sync"  # A not yet received at as_of -> cannot be used


def test_tolerance_2s() -> None:
    base = pd.Timestamp("2026-12-01T15:00:00Z")
    rows = []
    for sec, lag in [("sec_t", 0.0), ("sec_a", 2.0), ("sec_b", 2.5)]:
        ts = base + pd.Timedelta(seconds=3)
        q = ts - pd.Timedelta(seconds=0.1 + lag)
        rows.append(
            {
                "ts": ts,
                "security_id": sec,
                "quote_ts": q,
                "received_at": q,
                "bid": 99.99,
                "ask": 100.01,
                "halted": False,
                "luld_pause": False,
            }
        )
    ev = evaluate_quotes(pd.DataFrame(rows))
    r = find_first_sync_qualifying(base, "sec_t", ["sec_a", "sec_b"], 2000, 5, quotes=ev, max_missing=1)
    assert r.status == "ok" and r.missing_constituents == ("sec_b",)  # 2.0s ok, 2.5s too far
    r0 = find_first_sync_qualifying(base, "sec_t", ["sec_a", "sec_b"], 2000, 5, quotes=ev, max_missing=0)
    assert r0.status == "no_sync"
