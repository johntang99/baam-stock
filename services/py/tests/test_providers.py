"""Provider interface + fixture provider point-in-time guard."""

from datetime import date, timedelta

import pytest

from sr.marketdata.providers.base import MarketDataProvider
from sr.marketdata.providers.fixture import FixtureProvider
from sr.timeguard import LookaheadError
from tests.conftest import et

D = date(2026, 12, 1)


def test_fixture_provider_implements_protocol(fixture_path) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(FixtureProvider(fixture_path), MarketDataProvider)


def test_fixture_provider_refuses_future(fixture_path) -> None:  # type: ignore[no-untyped-def]
    p = FixtureProvider(fixture_path, as_of=et(D, "10:00"))
    assert len(p.quotes_1s(["NVDA"], et(D, "09:55"), et(D, "10:00"))) == 301
    with pytest.raises(LookaheadError):
        p.quotes_1s(["NVDA"], et(D, "09:55"), et(D, "10:00") + timedelta(seconds=1))
    with pytest.raises(LookaheadError):
        p.get_official_close("NVDA", D)


def test_bars_and_official_close(fixture_path) -> None:  # type: ignore[no-untyped-def]
    p = FixtureProvider(fixture_path)
    bars = p.get_bars("NVDA", et(D, "09:30"), et(D, "09:39:59"), "1m")
    assert bars.num_rows == 10 and set(bars.column_names) >= {"bar_start", "open", "high", "low", "close"}
    oc = p.get_official_close("NVDA", D)
    assert oc is not None and oc.source == "synthetic_fixture" and oc.price > 0
    assert p.get_official_close("NVDA", date(2026, 11, 26)) is None
