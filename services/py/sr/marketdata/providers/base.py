"""MarketDataProvider interface (MP §3.2). Vendor adapters (D-13, not selected) implement this; Phase 0 ships
only the synthetic Parquet fixture implementation. No real paid API is called and no keys are stored."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol, runtime_checkable

import pyarrow as pa


@dataclass(frozen=True)
class QuoteTick:
    symbol: str
    security_id: str
    quote_ts: datetime  # UTC exchange/SIP time
    received_at: datetime  # UTC
    bid: float
    ask: float
    last: float | None
    halted: bool = False
    luld_pause: bool = False


@dataclass(frozen=True)
class OfficialClose:
    security_id: str
    session_date: date
    price: float
    price_ts: datetime  # UTC
    source: str  # e.g. "nasdaq_official_close" or "synthetic_fixture"


@runtime_checkable
class MarketDataProvider(Protocol):
    def stream_quotes(self, symbols: list[str]) -> AsyncIterator[QuoteTick]: ...

    def get_bars(
        self, symbol: str, start_utc: datetime, end_utc: datetime, interval: Literal["1s", "1m"]
    ) -> pa.Table: ...

    def get_official_close(self, symbol: str, session_date: date) -> OfficialClose | None: ...
