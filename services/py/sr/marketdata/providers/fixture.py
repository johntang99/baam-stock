"""Parquet fixture provider (synthetic data from scripts/make_fixture.py; verification_status=proposed).

Point-in-time: construct with as_of to forbid reading data after that instant (raises LookaheadError).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from sr.calendar import get_calendar
from sr.marketdata.providers.base import OfficialClose, QuoteTick
from sr.timeguard import LookaheadError, ensure_utc


class FixtureProvider:
    source_id = "src_fixture_synthetic"

    def __init__(self, path: str | Path, as_of: datetime | None = None) -> None:
        self.path = Path(path)
        table = pq.read_table(self.path)
        meta = {k.decode(): v.decode() for k, v in (table.schema.metadata or {}).items()}
        self.metadata = meta
        self.synthetic = meta.get("synthetic") == "true"
        self._df = table.to_pandas()
        self.as_of = ensure_utc(as_of, "as_of") if as_of is not None else None

    # --- helpers ---------------------------------------------------------------------------------------
    def _check(self, end_utc: datetime) -> None:
        if self.as_of is not None and ensure_utc(end_utc, "end_utc") > self.as_of:
            raise LookaheadError(f"requested data up to {end_utc} after provider as_of {self.as_of}")

    def _sid(self, symbol: str) -> str:
        m = self._df.loc[self._df["symbol"] == symbol, "security_id"]
        if m.empty:
            if (self._df["security_id"] == symbol).any():
                return symbol
            raise KeyError(f"symbol {symbol!r} not in fixture")
        return str(m.iloc[0])

    @property
    def symbols(self) -> list[str]:
        return sorted(self._df["symbol"].unique().tolist())

    def quotes_1s(self, symbols: list[str], start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
        """1-second layer rows with ts in [start, end] (the frame quote_rules.evaluate_quotes expects)."""
        self._check(end_utc)
        s, e = ensure_utc(start_utc, "start_utc"), ensure_utc(end_utc, "end_utc")
        sids = [self._sid(x) for x in symbols]
        d = self._df
        out: pd.DataFrame = d[d["security_id"].isin(sids) & (d["ts"] >= s) & (d["ts"] <= e)].reset_index(
            drop=True
        )
        return out

    # --- MarketDataProvider ----------------------------------------------------------------------------
    async def stream_quotes(self, symbols: list[str]) -> AsyncIterator[QuoteTick]:  # replay, not live
        df = self._df[self._df["symbol"].isin(symbols)].sort_values("ts")
        if self.as_of is not None:
            df = df[df["ts"] <= self.as_of]
        for r in df.itertuples(index=False):
            yield QuoteTick(
                r.symbol,
                r.security_id,
                r.quote_ts.to_pydatetime(),
                r.received_at.to_pydatetime(),
                float(r.bid),
                float(r.ask),
                float(r.last),
                bool(r.halted),
                bool(r.luld_pause),
            )

    def get_bars(
        self, symbol: str, start_utc: datetime, end_utc: datetime, interval: Literal["1s", "1m"]
    ) -> pa.Table:
        q = self.quotes_1s([symbol], start_utc, end_utc)
        q = q.assign(mid=(q["bid"] + q["ask"]) / 2)
        if interval == "1s":
            return pa.Table.from_pandas(q, preserve_index=False)
        bars = q.set_index("ts")["mid"].resample("1min", label="left", closed="left").ohlc().dropna()
        bars.index.name = "bar_start"
        return pa.Table.from_pandas(bars.reset_index(), preserve_index=False)

    def get_official_close(self, symbol: str, session_date: date) -> OfficialClose | None:
        """Synthetic stand-in: last NBBO mid at or before the session close (a real vendor returns the
        listing exchange's official closing price, D-11)."""
        s = get_calendar().session(session_date)
        if not s.is_open or s.close_at is None:
            return None
        self._check(s.close_at)
        sid = self._sid(symbol)
        d = self._df[(self._df["security_id"] == sid) & (self._df["ts"] <= s.close_at)]
        d = d[(d["bid"] > 0) & (d["ask"] > d["bid"])]
        if d.empty:
            return None
        r = d.iloc[-1]
        return OfficialClose(
            sid, session_date, float((r["bid"] + r["ask"]) / 2), r["ts"].to_pydatetime(), "synthetic_fixture"
        )
