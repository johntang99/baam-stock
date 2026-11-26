"""Generate the SYNTHETIC (虚构) 1-second NBBO fixture for Phase 0 tests.

NVDA + its 11 semis_peer_v1 constituents + reference symbols (QQQ, SPY, SMH, SOXX, ^VIX),
2026-12-01 09:30:00–16:00:00 ET, one row per symbol per second. Prices are random walks — NOT market data.
Injected anomalies (also stored in the Parquet metadata and data/fixtures/<name>.manifest.json):
  - NVDA wide spread 11:00:00–11:01:59 ET (35bp)
  - NVDA trading halt 13:15:00–13:17:59 ET (3 minutes; quotes frozen, halted=true)
  - INTC stale quote 10:20:10–10:20:39 ET (no NBBO update => age > 5s)
  - AMD and MU LULD pause 14:40:00–14:41:29 ET (two constituents missing at once)

Usage: uv run python scripts/make_fixture.py [--out data/fixtures/nvda_2026-12-01_1s.parquet] [--seed 20261201]
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from sr.calendar.calendar import ET, get_calendar
from sr.config import load, repo_root

SESSION = date(2026, 12, 1)
REFERENCE = ["QQQ", "SPY", "SMH", "SOXX", "^VIX"]
BASE = {"NVDA": 182.4, "AMD": 214.1, "AVGO": 352.8, "MU": 118.6, "QCOM": 171.2, "TXN": 168.9, "INTC": 37.4,
        "ADI": 241.7, "MRVL": 92.3, "AMAT": 205.5, "LRCX": 101.8, "KLAC": 812.0, "QQQ": 512.3, "SPY": 603.1,
        "SMH": 268.4, "SOXX": 243.9, "^VIX": 16.2}   # fictional levels
BETA = {"^VIX": -4.0, "QQQ": 0.6, "SPY": 0.45, "SMH": 1.0, "SOXX": 1.0}


def et(t: str) -> pd.Timestamp:
    h, m, s = (int(x) for x in t.split(":"))
    return pd.Timestamp(datetime.combine(SESSION, time(h, m, s), tzinfo=ET)).tz_convert("UTC")


ANOMALIES = [
    {"kind": "wide_spread", "symbol": "NVDA", "start_et": "11:00:00", "end_et": "11:01:59", "spread_bp": 35},
    {"kind": "halt", "symbol": "NVDA", "start_et": "13:15:00", "end_et": "13:17:59"},
    {"kind": "stale", "symbol": "INTC", "start_et": "10:20:10", "end_et": "10:20:39"},
    {"kind": "luld_pause", "symbol": "AMD", "start_et": "14:40:00", "end_et": "14:41:29"},
    {"kind": "luld_pause", "symbol": "MU", "start_et": "14:40:00", "end_et": "14:41:29"},
]


def sid(sym: str) -> str:
    return "sec_" + sym.lower().lstrip("^")


def build(seed: int) -> tuple[pd.DataFrame, dict[str, object]]:
    s = get_calendar().session(SESSION)
    assert s.open_at and s.close_at
    grid = pd.date_range(s.open_at, s.close_at, freq="1s", tz="UTC")
    n = len(grid)
    rng = np.random.default_rng(seed)
    peers = load("benchmarks")["semis_peer_v1"]["constituents"]
    symbols = [*peers, *REFERENCE]
    sector = np.cumsum(rng.normal(0, 0.00008, n))
    frames = []
    for sym in symbols:
        beta = BETA.get(sym, rng.uniform(0.8, 1.4))
        idio = np.cumsum(rng.normal(0, 0.00007, n))
        mid = BASE[sym] * np.exp(beta * sector + idio)
        spread_bp = rng.uniform(0.6, 2.2, n)
        upd = rng.random(n) < 0.95
        upd[0] = True
        halted = np.zeros(n, bool)
        luld = np.zeros(n, bool)
        for a in ANOMALIES:
            if a["symbol"] != sym:
                continue
            m = (grid >= et(a["start_et"])) & (grid <= et(a["end_et"]))
            if a["kind"] == "wide_spread":
                spread_bp[m] = a["spread_bp"]
            elif a["kind"] == "stale":
                upd[m] = False
            elif a["kind"] == "halt":
                halted[m] = True
                upd[m] = False
            elif a["kind"] == "luld_pause":
                luld[m] = True
        half = mid * spread_bp / 2e4
        bid = np.floor((mid - half) * 100) / 100
        ask = np.ceil((mid + half) * 100) / 100
        ask = np.where(ask <= bid, bid + 0.01, ask)
        # quote_ts: time of the NBBO in effect; frozen (with bid/ask) when no update
        offs = pd.to_timedelta(rng.integers(0, 900, n), unit="ms")
        idx = pd.Series(np.where(upd, np.arange(n), np.nan)).ffill().astype(int).to_numpy()
        qts = (grid - offs).take(idx)
        bid, ask = bid[idx], ask[idx]
        recv = qts + pd.to_timedelta(rng.integers(20, 250, n), unit="ms")
        last = np.round((bid + ask) / 2 + rng.normal(0, 0.003, n), 2)
        frames.append(pd.DataFrame({
            "ts": grid, "symbol": sym, "security_id": sid(sym),
            "quote_ts": qts, "received_at": recv,
            "bid": bid, "ask": ask, "last": last, "halted": halted, "luld_pause": luld,
        }))
    df = pd.concat(frames, ignore_index=True)
    meta = {"synthetic": "true", "label": "SYNTHETIC / 虚构 — not market data", "generator": "scripts/make_fixture.py",
            "seed": seed, "session_date": SESSION.isoformat(), "symbols": symbols, "anomalies": ANOMALIES,
            "quote_rule_version_hint": "qr-0.1", "vendor_source_id": "src_fixture_synthetic"}
    return df, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(repo_root() / "data/fixtures/nvda_2026-12-01_1s.parquet"))
    ap.add_argument("--seed", type=int, default=20261201)
    a = ap.parse_args()
    df, meta = build(a.seed)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({**(table.schema.metadata or {}),
                                           **{k: (v if isinstance(v, str) else json.dumps(v)) for k, v in meta.items()}})
    pq.write_table(table, out, compression="zstd")
    out.with_suffix(".manifest.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out} ({len(df):,} rows, {len(meta['symbols'])} symbols) — SYNTHETIC")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
