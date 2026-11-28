"""DP 2.01 md-ingest: 1-second layer, look-ahead guard, outage -> stale, latency metrics, Parquet parts. SYNTHETIC."""

import asyncio
from datetime import date, datetime, time, timedelta

import pandas as pd
import pyarrow.parquet as pq
import pytest

from sr.calendar.calendar import et_to_utc
from sr.marketdata.live import LiveIngest, LiveQuoteStore, Outage, SimulatedFeed, advance
from sr.marketdata.quote_rules import evaluate_quotes
from sr.timeguard import LookaheadError

DAY = date(2026, 12, 1)
SYMS = {"NVDA": "sec_nvda", "AMD": "sec_amd"}


class Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t


def build(raw: pd.DataFrame, until: datetime, outages=(), flush_dir=None):  # type: ignore[no-untyped-def]
    clock = Clock(until)
    store = LiveQuoteStore(clock, "src_fixture_synthetic", synthetic=True)
    ing = LiveIngest(store, SYMS, flush_dir=flush_dir)
    feed = SimulatedFeed(raw, SYMS, outages)
    start = et_to_utc(DAY, time(9, 30))
    t = start
    while t <= until:  # deliver in 30 s steps, as the live loop does
        clock.t = t
        advance(feed, ing, t)
        t += timedelta(seconds=30)
    clock.t = until
    advance(feed, ing, until)
    return store, ing, clock


def test_layer_matches_the_recorded_1s_layer(raw_quotes) -> None:  # type: ignore[no-untyped-def]
    until = et_to_utc(DAY, time(10, 5))
    store, _, _ = build(raw_quotes, until)
    a, b = et_to_utc(DAY, time(10, 0)), until
    got = store.quotes_1s(["sec_nvda"], a, b).set_index("ts")
    want = raw_quotes[(raw_quotes["security_id"] == "sec_nvda") & raw_quotes["ts"].between(a, b)].set_index(
        "ts"
    )
    assert len(got) == len(want) == 301
    # The recorded layer keys rows by quote_ts, so a row can hold a tick received a few ms after its second.
    # Live only shows what was received by the second: those rows hold the previous quote instead.
    seen = want["received_at"] <= want.index.to_series()
    assert seen.mean() > 0.8
    for c in ("quote_ts", "bid", "ask"):
        assert (got.loc[seen, c] == want.loc[seen, c]).all(), c
    assert (got.loc[~seen, "quote_ts"] < want.loc[~seen, "quote_ts"]).all()
    assert (got["received_at"] <= got.index.to_series()).all()  # never a tick before it was received


def test_reading_past_the_clock_is_refused(raw_quotes) -> None:  # type: ignore[no-untyped-def]
    until = et_to_utc(DAY, time(9, 40))
    store, _, _ = build(raw_quotes, until)
    with pytest.raises(LookaheadError):
        store.quotes_1s(["sec_nvda"], until - timedelta(minutes=1), until + timedelta(seconds=1))


def test_outage_repeats_the_old_quote_and_it_stops_qualifying(raw_quotes) -> None:  # type: ignore[no-untyped-def]
    o0, o1 = et_to_utc(DAY, time(10, 0)), et_to_utc(DAY, time(10, 2))
    store, ing, _ = build(raw_quotes, et_to_utc(DAY, time(10, 3)), outages=[Outage(o0, o1)])
    q = evaluate_quotes(
        store.quotes_1s(["sec_nvda", "sec_amd"], o0 - timedelta(minutes=20), o1 + timedelta(seconds=30))
    )
    mid = q[(q["ts"] > o0 + timedelta(seconds=10)) & (q["ts"] < o1)]
    assert len(mid) > 0 and not mid["is_qualifying"].any()  # age > 5 s: stale quotes
    assert (mid["quote_ts"] < o0).all()
    after = q[q["ts"] > o1 + timedelta(seconds=5)]
    assert after["is_qualifying"].any()  # recovers when ticks resume
    _, during, _ = build(raw_quotes, o0 + timedelta(seconds=90), outages=[Outage(o0, o1)])
    assert set(during.metrics(o0 + timedelta(seconds=90))["stale_symbols"]) == {"NVDA", "AMD"}


def test_latency_metrics_from_vendor_timestamps(raw_quotes) -> None:  # type: ignore[no-untyped-def]
    _, ing, clock = build(raw_quotes, et_to_utc(DAY, time(9, 45)))
    m = ing.metrics(clock())
    assert 20 <= m["latency_p50_ms"] <= m["latency_p95_ms"] <= 250  # the fixture's received_at - quote_ts
    assert m["symbols"]["NVDA"]["n"] > 0 and m["stale_symbols"] == []


def test_flush_writes_immutable_synthetic_parts(raw_quotes, tmp_path) -> None:  # type: ignore[no-untyped-def]
    store, ing, clock = build(raw_quotes, et_to_utc(DAY, time(9, 35)), flush_dir=tmp_path)
    p1 = ing.flush()
    assert p1 is not None and p1.parent.name == "2026-12-01"
    t = pq.read_table(p1)
    assert t.schema.metadata[b"synthetic"] == b"true" and t.num_rows == len(store.frame())
    clock.t = et_to_utc(DAY, time(9, 36))
    ing.advance_to(clock.t)
    p2 = ing.flush()
    assert p2 is not None and p2 != p1 and pq.read_table(p1).num_rows == t.num_rows  # p1 untouched
    assert ing.flush() is None  # nothing new


def test_simulated_feed_streams_ticks_in_arrival_order(raw_quotes) -> None:  # type: ignore[no-untyped-def]
    small = raw_quotes[raw_quotes["ts"] < et_to_utc(DAY, time(9, 31))]
    feed = SimulatedFeed(small, ["NVDA"])

    async def take() -> list:  # type: ignore[type-arg]
        return [k async for k in feed.stream_quotes(["NVDA"])]

    ticks = asyncio.run(take())
    assert ticks and all(a.received_at <= b.received_at for a, b in zip(ticks, ticks[1:], strict=False))
    assert len({k.quote_ts for k in ticks}) == len(ticks)  # re-sends collapsed


def test_parquet_store_reads_flushed_parts(raw_quotes, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from sr.marketdata.live import ParquetQuoteStore

    store, ing, clock = build(raw_quotes, et_to_utc(DAY, time(9, 40)), flush_dir=tmp_path)
    ing.flush()
    ps = ParquetQuoteStore(tmp_path, clock)
    a = et_to_utc(DAY, time(9, 35))
    got = ps.quotes_1s(["sec_nvda"], a, clock())
    want = store.quotes_1s(["sec_nvda"], a, clock())
    assert ps.security_ids == {"sec_nvda", "sec_amd"} and ps.synthetic is True
    assert len(got) == len(want) and (got["quote_ts"].to_numpy() == want["quote_ts"].to_numpy()).all()
    clock.t = et_to_utc(DAY, time(9, 41))
    ing.advance_to(clock.t)
    ing.flush()
    assert len(ps.quotes_1s(["sec_nvda"], a, clock.t)) == len(want) + 60  # the new part is picked up
    with pytest.raises(LookaheadError):
        ps.quotes_1s(["sec_nvda"], a, clock.t + timedelta(seconds=1))


def test_cli_live_dry_run(fixture_path, capsys) -> None:  # type: ignore[no-untyped-def]
    import json

    from sr.cli import main

    assert (
        main(
            ["live", "--dry-run", "--symbols", "NVDA,AMD", "--fixture", str(fixture_path), "--until", "09:45"]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["synthetic"] is True and out["symbols"] == ["NVDA", "AMD"]
    assert out["planned_snapshot_jobs"] == 2 * 5  # 09:30, 09:35, 09:35 session check, 09:40, 09:45
    assert out["metrics"]["latency_p95_ms"] <= 250
    assert main(["live", "--symbols", "NVDA"]) == 2  # no vendor feed (D-13)
