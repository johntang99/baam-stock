"""Live market data: md-ingest, the 1-second layer, Parquet flush and latency metrics (DP 2.01; MP §3.2; OQ-58).

- `LiveIngest` takes vendor ticks (`QuoteTick`, any `MarketDataProvider.stream_quotes`) and builds the same
  1-second layer the fixture has: at each second boundary S, one row per symbol holding the latest tick *received*
  by S (`ts = S`). With no new tick the row repeats the old quote, so its age (`ts - quote_ts`) grows and quote
  rules mark it non-qualifying. That is how an outage turns into `stale` (AC-18).
- `LiveQuoteStore` serves that layer through `quotes_1s()`, the read used by snapshots, forecasts and settlement.
  A read past the store clock raises LookaheadError: live code can never see a second that has not happened.
- `flush()` appends immutable Parquet part files `<dir>/<session_date>/part-<first ts>.parquet`.
- `metrics()`: per-symbol and overall vendor latency (`received_at - quote_ts`) p50 / p95 and last-tick age.

`SimulatedFeed` replays a recorded 1-second fixture as a tick stream (synthetic, 虚构). Outage windows drop ticks,
for tests and drills. No vendor is wired in: the D-13 adapter goes in `sr/marketdata/providers/<vendor>.py`.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from sr.calendar import get_calendar
from sr.config import load
from sr.marketdata.providers.base import OfficialClose, QuoteTick
from sr.timeguard import LookaheadError, ensure_utc

COLUMNS = (
    "ts",
    "symbol",
    "security_id",
    "quote_ts",
    "received_at",
    "bid",
    "ask",
    "last",
    "halted",
    "luld_pause",
)
UTC_COLS = ("ts", "quote_ts", "received_at")


def _ts(t: datetime | pd.Timestamp) -> pd.Timestamp:
    return ensure_utc(t, "t")


def _empty() -> pd.DataFrame:
    return pd.DataFrame(
        {c: pd.Series(dtype="datetime64[ns, UTC]" if c in UTC_COLS else "object") for c in COLUMNS}
    )


# ---------------------------------------------------------------- store
class LiveQuoteStore:
    """In-memory 1-second layer. `clock()` is the store's notion of now (wall clock live, simulated in replay)."""

    def __init__(
        self,
        clock: Callable[[], datetime],
        source_id: str,
        synthetic: bool,
        official_closes: dict[tuple[str, date], float] | None = None,
    ) -> None:
        self.clock, self.source_id, self.synthetic = clock, source_id, synthetic
        self._chunks: list[pd.DataFrame] = []
        self._pending: list[tuple[Any, ...]] = []
        self._frame: pd.DataFrame | None = None
        self._ids: set[str] = set()
        self.closes = dict(official_closes or {})

    def append_rows(self, rows: list[tuple[Any, ...]]) -> None:
        if rows:
            self._pending += rows
            self._ids.update(r[2] for r in rows)

    def frame(self) -> pd.DataFrame:
        if self._pending:
            df = pd.DataFrame(self._pending, columns=list(COLUMNS))
            for c in UTC_COLS:
                df[c] = pd.to_datetime(df[c], utc=True)
            self._chunks.append(df)
            self._pending = []
            self._frame = None
        if self._frame is None:
            self._frame = pd.concat(self._chunks, ignore_index=True) if self._chunks else _empty()
        return self._frame

    @property
    def security_ids(self) -> set[str]:
        return set(self._ids)

    def quotes_1s(self, ids: list[str], start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
        end = _ts(end_utc)
        now = _ts(self.clock())
        if end > now:
            raise LookaheadError(f"live store read up to {end} but the clock is {now}")
        d = self.frame()
        m = (d["ts"] >= _ts(start_utc)) & (d["ts"] <= end) & d["security_id"].isin(ids)
        return d.loc[m].sort_values(["security_id", "ts"]).reset_index(drop=True)

    def get_official_close(self, security_id: str, session_date: date) -> OfficialClose | None:
        p = self.closes.get((security_id, session_date))
        if p is None:
            return None
        s = get_calendar().session(session_date)
        assert s.close_at is not None
        return OfficialClose(security_id, session_date, float(p), s.close_at, self.source_id)


class ParquetQuoteStore(LiveQuoteStore):
    """The 1-second layer as flushed by md-ingest (`<root>/<session_date>/part-*.parquet`), for a worker process
    that does not share md-ingest's memory. New parts are picked up on each read; parts are immutable."""

    def __init__(self, root: Path, clock: Callable[[], datetime]) -> None:
        super().__init__(clock, source_id="unknown", synthetic=True)
        self.root = Path(root)
        self._seen: set[Path] = set()

    def frame(self) -> pd.DataFrame:
        new = sorted(p for p in self.root.glob("*/part-*.parquet") if p not in self._seen)
        for p in new:
            t = pq.read_table(p)
            meta = {k.decode(): v.decode() for k, v in (t.schema.metadata or {}).items()}
            self.source_id = meta.get("source_id", self.source_id)
            self.synthetic = self.synthetic and meta.get("synthetic") == "true"
            df = t.to_pandas()
            self._chunks.append(df[list(COLUMNS)])
            self._ids.update(df["security_id"].unique().tolist())
            self._seen.add(p)
        if new:
            self._frame = None
        return super().frame()

    @property
    def security_ids(self) -> set[str]:
        self.frame()
        return set(self._ids)


# ---------------------------------------------------------------- ingest
@dataclass
class _Lat:
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=5000))
    last_received_at: pd.Timestamp | None = None
    last_quote_ts: pd.Timestamp | None = None
    n: int = 0
    out_of_order: int = 0


class LiveIngest:
    """Tick inbox -> 1-second layer. Feed ticks with on_tick(), then advance_to(now) emits every whole second up to
    now, applying only ticks received by each second (a tick is never visible before its received_at)."""

    def __init__(self, store: LiveQuoteStore, symbols: dict[str, str], flush_dir: Path | None = None) -> None:
        self.store, self.symbols, self.flush_dir = store, dict(symbols), flush_dir
        self._inbox: list[QuoteTick] = []
        self._last: dict[str, QuoteTick] = {}
        self._emitted_to: pd.Timestamp | None = None
        self._unflushed: list[tuple[Any, ...]] = []
        self.lat: dict[str, _Lat] = {s: _Lat() for s in self.symbols}
        self.parts: list[Path] = []

    def on_tick(self, tick: QuoteTick) -> None:
        if tick.symbol in self.symbols:
            self._inbox.append(tick)

    def advance_to(self, now: datetime) -> int:
        """Emit the 1-second rows for every second S with last_emitted < S <= now. Returns rows emitted."""
        end = _ts(now).floor("1s")
        self._inbox.sort(key=lambda k: k.received_at)
        if self._emitted_to is None:
            if not self._inbox:
                return 0
            self._emitted_to = _ts(self._inbox[0].received_at).floor("1s")
        rows: list[tuple[Any, ...]] = []
        i = 0
        s = self._emitted_to + pd.Timedelta(seconds=1)
        while s <= end:
            while i < len(self._inbox) and _ts(self._inbox[i].received_at) <= s:
                self._apply(self._inbox[i])
                i += 1
            for sym, k in self._last.items():
                rows.append(
                    (
                        s,
                        sym,
                        k.security_id,
                        k.quote_ts,
                        k.received_at,
                        k.bid,
                        k.ask,
                        k.last,
                        k.halted,
                        k.luld_pause,
                    )
                )
            s += pd.Timedelta(seconds=1)
        self._inbox = self._inbox[i:]
        self._emitted_to = max(self._emitted_to, end)
        self.store.append_rows(rows)
        self._unflushed += rows
        return len(rows)

    def _apply(self, k: QuoteTick) -> None:
        prev = self._last.get(k.symbol)
        lt = self.lat[k.symbol]
        if prev is not None and _ts(k.quote_ts) < _ts(
            prev.quote_ts
        ):  # older quote arriving late: never go back
            lt.out_of_order += 1
            return
        self._last[k.symbol] = k
        if prev is None or prev.quote_ts != k.quote_ts:  # a new quote, not a re-send
            lt.samples.append((_ts(k.received_at) - _ts(k.quote_ts)).total_seconds() * 1000.0)
            lt.n += 1
            lt.last_quote_ts = _ts(k.quote_ts)
        lt.last_received_at = _ts(k.received_at)

    # -- persistence
    def flush(self) -> Path | None:
        if not self._unflushed or self.flush_dir is None:
            return None
        df = pd.DataFrame(self._unflushed, columns=list(COLUMNS))
        for c in UTC_COLS:
            df[c] = pd.to_datetime(df[c], utc=True)
        first = df["ts"].min()
        day = get_calendar().session_for_instant(first.to_pydatetime()).session_date
        d = self.flush_dir / day.isoformat()
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"part-{first.strftime('%Y%m%dT%H%M%SZ')}.parquet"
        if p.exists():  # parts are immutable: a second flush in the same second gets a suffix
            p = d / f"part-{first.strftime('%Y%m%dT%H%M%SZ')}-{len(self.parts)}.parquet"
        t = pa.Table.from_pandas(df, preserve_index=False)
        meta = {
            b"synthetic": str(self.store.synthetic).lower().encode(),
            b"source_id": self.store.source_id.encode(),
            b"layer": b"1s",
        }
        pq.write_table(t.replace_schema_metadata({**(t.schema.metadata or {}), **meta}), p)
        self._unflushed = []
        self.parts.append(p)
        return p

    # -- metrics
    def metrics(self, now: datetime) -> dict[str, Any]:
        t = _ts(now)
        per: dict[str, Any] = {}
        allv: list[float] = []
        for sym, lt in self.lat.items():
            v = list(lt.samples)
            allv += v
            per[sym] = {
                "n": lt.n,
                "out_of_order": lt.out_of_order,
                "latency_p50_ms": float(np.percentile(v, 50)) if v else None,
                "latency_p95_ms": float(np.percentile(v, 95)) if v else None,
                "last_quote_age_s": None
                if lt.last_quote_ts is None
                else round((t - lt.last_quote_ts).total_seconds(), 3),
            }
        stale_s = float(load("snapshot")["quality"]["stale_after_s"])
        return {
            "source_id": self.store.source_id,
            "latency_p50_ms": float(np.percentile(allv, 50)) if allv else None,
            "latency_p95_ms": float(np.percentile(allv, 95)) if allv else None,
            "stale_symbols": sorted(
                s for s, m in per.items() if m["last_quote_age_s"] is None or m["last_quote_age_s"] > stale_s
            ),
            "symbols": per,
        }


# ---------------------------------------------------------------- simulated feed (synthetic)
@dataclass(frozen=True)
class Outage:
    start: datetime
    end: datetime
    symbols: tuple[str, ...] | None = None  # None: the whole feed


class SimulatedFeed:
    """Replays a recorded 1-second layer as distinct ticks in received_at order (SYNTHETIC / 虚构 data only)."""

    source_id = "src_fixture_synthetic"

    def __init__(self, raw: pd.DataFrame, symbols: Iterable[str], outages: Iterable[Outage] = ()) -> None:
        d = raw[raw["symbol"].isin(list(symbols))].sort_values("received_at")
        d = d.drop_duplicates(["symbol", "quote_ts"], keep="first")
        for o in outages:
            m = (d["received_at"] >= _ts(o.start)) & (d["received_at"] < _ts(o.end))
            if o.symbols is not None:
                m &= d["symbol"].isin(list(o.symbols))
            d = d[~m]
        self._d = d.reset_index(drop=True)
        self._recv = self._d["received_at"].dt.tz_convert(None).to_numpy()
        self._pos = 0

    def ticks_until(self, t: datetime) -> list[QuoteTick]:
        end = np.searchsorted(
            self._recv, np.datetime64(_ts(t).tz_convert(None).to_datetime64()), side="right"
        )
        chunk = self._d.iloc[self._pos : end]
        self._pos = int(end)
        recs: list[dict[str, Any]] = chunk.to_dict("records")  # type: ignore[assignment]
        return [
            QuoteTick(
                str(r["symbol"]),
                str(r["security_id"]),
                r["quote_ts"],
                r["received_at"],
                float(r["bid"]),
                float(r["ask"]),
                None if pd.isna(r["last"]) else float(r["last"]),
                bool(r["halted"]),
                bool(r["luld_pause"]),
            )
            for r in recs
        ]

    async def stream_quotes(self, symbols: list[str]) -> AsyncIterator[QuoteTick]:
        for k in self.ticks_until(pd.Timestamp.max.tz_localize("UTC")):
            if k.symbol in symbols:
                yield k

    def get_bars(
        self, symbol: str, start_utc: datetime, end_utc: datetime, interval: Literal["1s", "1m"]
    ) -> pa.Table:
        raise NotImplementedError("the simulated feed only streams ticks")

    def get_official_close(self, symbol: str, session_date: date) -> OfficialClose | None:
        return None


def advance(feed: SimulatedFeed, ingest: LiveIngest, now: datetime) -> int:
    """Deliver every tick received by `now`, then emit the 1-second rows up to now."""
    for k in feed.ticks_until(now):
        ingest.on_tick(k)
    return ingest.advance_to(now)


def step_seconds(start: datetime, end: datetime, every_s: float) -> list[datetime]:
    out, t = [], _ts(start).to_pydatetime()
    while t <= end:
        out.append(t)
        t += timedelta(seconds=every_s)
    return out
