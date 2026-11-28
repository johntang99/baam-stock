"""Market reaction for an event analysis (DP 1.09; DC market_reaction; AC-10, AC-40; OQ-43).

From the 1-second reference-quote layer (already evaluated by quote_rules.evaluate_quotes):
- sync points: seconds where the stock has a qualifying quote and the peer basket constituents (all but at most
  `max_missing`) have qualifying quotes within the sync tolerance of it (D-06; same rule as sync.py);
- ref_before = last sync point strictly before the evidence's earliest public time; ref_asof = last sync point at
  or before analysis_as_of; stock / basket / relative return between them (relative = stock − basket);
- the basket unavailable -> absolute return from qualifying stock quotes only, relative = null (AC-40);
- move start: the opposite extreme of the relative path over the lookback before analysis_as_of (OQ-43), used by
  the reasoning timing check (news later than the move start is never its cause, AC-10).

Point in time: any quote received after analysis_as_of raises LookaheadError — callers pass only what was visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sr.benchmark.basket import basket_return, equal_weights
from sr.calendar import get_calendar
from sr.config import load
from sr.db import Conn
from sr.events.reasoning import MarketMove
from sr.timeguard import assert_not_after, ensure_utc


@dataclass(frozen=True)
class RefPoint:
    ts: pd.Timestamp
    stock: dict[str, Any]
    constituents: dict[str, dict[str, Any]]  # qualifying + within tolerance only


@dataclass(frozen=True)
class Reaction:
    market_reaction: dict[str, Any]  # DC fields exactly
    move: MarketMove | None  # None when no stock quote is available
    quote_rows: list[dict[str, Any]] = field(default_factory=list)  # reference_quotes rows to persist
    detail: dict[str, Any] = field(default_factory=dict)


def quote_id(security_id: str, ts: pd.Timestamp) -> str:
    """rq_<ticker>_<yyyymmdd>_<hhmmss> (UTC sample second), as in the DC §8 example."""
    t = ensure_utc(ts, "ts")
    return f"rq_{security_id.removeprefix('sec_')}_{t:%Y%m%d_%H%M%S}"


def _sync_cfg() -> dict[str, Any]:
    return dict(load("quote_rules")["sync"])


def sync_points(
    quotes: pd.DataFrame,
    security: str,
    basket: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    tolerance_ms: int | None = None,
    max_missing: int | None = None,
) -> list[RefPoint]:
    """All sync points with start <= ts <= end, oldest first."""
    sc = _sync_cfg()
    tol = pd.Timedelta(milliseconds=int(sc["tolerance_ms"]) if tolerance_ms is None else tolerance_ms)
    mm = int(sc["max_missing_constituents"]) if max_missing is None else max_missing
    win = quotes[(quotes["ts"] >= start) & (quotes["ts"] <= end) & quotes["is_qualifying"]]
    tgt = win[win["security_id"] == security].sort_values("ts")
    if tgt.empty:
        return []
    cons = win[win["security_id"].isin(basket)]
    by_c = {c: g.set_index("ts") for c, g in cons.groupby("security_id")}
    out = []
    for row in tgt.to_dict("records"):
        ts, qts = row["ts"], row["quote_ts"]
        got: dict[str, dict[str, Any]] = {}
        for c in basket:
            g = by_c.get(c)
            if g is not None and ts in g.index:
                cr = g.loc[ts]
                if abs(cr["quote_ts"] - qts) <= tol:
                    got[c] = {str(k): v for k, v in cr.to_dict().items()} | {"ts": ts, "security_id": c}
        if len(basket) - len(got) <= mm:
            out.append(RefPoint(ts, {str(k): v for k, v in row.items()}, got))
    return out


def _stock_only(
    quotes: pd.DataFrame, security: str, start: pd.Timestamp, end: pd.Timestamp
) -> list[RefPoint]:
    q = quotes[
        (quotes["security_id"] == security)
        & (quotes["ts"] >= start)
        & (quotes["ts"] <= end)
        & quotes["is_qualifying"]
    ].sort_values("ts")
    return [RefPoint(r["ts"], {str(k): v for k, v in r.items()}, {}) for r in q.to_dict("records")]


def _ret_pct(p0: float, p1: float) -> float:
    return (p1 / p0 - 1.0) * 100.0


def _basket_ret(a: RefPoint, b: RefPoint, weights: dict[str, float]) -> tuple[float | None, tuple[str, ...]]:
    br = basket_return(
        {c: a.constituents.get(c, {}).get("mid") for c in weights},
        {c: b.constituents.get(c, {}).get("mid") for c in weights},
        weights,
    )
    return (br.return_pct if br.status == "ok" else None), br.missing


def move_start(
    points: list[RefPoint], weights: dict[str, float] | None, min_move_pp: float
) -> tuple[pd.Timestamp | None, float]:
    """(start, move_pp). The opposite extreme of the relative path (stock alone without weights); latest on ties.
    Returns (None, move) when the move from the extreme to the last point is below min_move_pp."""
    if len(points) < 2:
        return None, 0.0
    first, path = points[0], []
    for p in points:
        s = _ret_pct(float(first.stock["mid"]), float(p.stock["mid"]))
        if weights:
            b, _ = _basket_ret(first, p, weights)
            if b is None:
                continue  # this point's basket is not computable; skip it on the relative path
            s -= b
        path.append((p.ts, s))
    if len(path) < 2:
        return None, 0.0
    last = path[-1][1]
    if last < 0:  # a fall: start at the highest level before it
        ext = max(v for _, v in path[:-1])
        ts = max(t for t, v in path[:-1] if v == ext)
    else:  # a rise (or flat): start at the lowest level
        ext = min(v for _, v in path[:-1])
        ts = max(t for t, v in path[:-1] if v == ext)
    move = last - ext
    if abs(move) < min_move_pp:
        return None, move
    return ts, move


def _session_type(ts: pd.Timestamp) -> str:
    s = get_calendar().session_for_instant(ts.to_pydatetime())
    if not s.is_open or s.open_at is None or s.close_at is None:
        return "post_market"
    t = ts.to_pydatetime()
    if t < s.open_at:
        return "pre_market"
    return "regular" if t < s.close_at else "post_market"


def _quote_row(r: dict[str, Any], ts: pd.Timestamp, vendor: str, rule_version: str) -> dict[str, Any]:
    sid = str(r["security_id"])
    return {
        "quote_id": quote_id(sid, ts),
        "security_id": sid,
        "quote_ts": ensure_utc(r["quote_ts"], "quote_ts").to_pydatetime(),
        "received_at": ensure_utc(r["received_at"], "received_at").to_pydatetime(),
        "session_type": _session_type(ts),
        "bid": float(r["bid"]),
        "ask": float(r["ask"]),
        "mid": float(r["mid"]),
        "last": None if pd.isna(r.get("last")) else float(r["last"]),
        "spread_bp": None if pd.isna(r.get("spread_bp")) else float(r["spread_bp"]),
        "price_type": "nbbo_mid",
        "quality_flags": list(r.get("quality_flags") or []),
        "is_qualifying": bool(r["is_qualifying"]),
        "quote_rule_version": rule_version,
        "vendor_source_id": vendor,
    }


def compute_reaction(
    quotes: pd.DataFrame,
    security: str,
    basket: list[str],
    anchor_at: datetime,
    analysis_as_of: datetime,
    weights: dict[str, float] | None = None,
    vendor_source_id: str | None = None,
) -> Reaction:
    """`anchor_at` = the earliest public time of the event's evidence (ref_before is the last sync point before it)."""
    cfg = load("reaction")
    as_of = ensure_utc(analysis_as_of, "analysis_as_of")
    anchor = ensure_utc(anchor_at, "anchor_at")
    if anchor > as_of:
        raise ValueError(f"anchor {anchor.isoformat()} is after analysis_as_of {as_of.isoformat()}")
    assert_not_after(quotes["received_at"], as_of, "quotes")  # never read what was not yet received
    assert_not_after(quotes["ts"], as_of, "quotes")
    w = weights or equal_weights([c for c in basket if c != security])
    members = list(w)
    rule_version = str(load("quote_rules")["quote_rule_version"])
    vendor = vendor_source_id or str(cfg["vendor_source_id"])
    back = pd.Timedelta(seconds=int(cfg["ref_before"]["max_lookback_s"]))
    stale = pd.Timedelta(seconds=int(cfg["ref_asof"]["max_staleness_s"]))

    before = [p for p in sync_points(quotes, security, members, anchor - back, as_of) if p.ts < anchor]
    after = [p for p in sync_points(quotes, security, members, as_of - stale, as_of)]
    synced = bool(before and after)
    if not synced:  # AC-40: absolute return from the stock alone, relative unavailable
        before = [p for p in _stock_only(quotes, security, anchor - back, as_of) if p.ts < anchor]
        after = _stock_only(quotes, security, as_of - stale, as_of)
    if not (before and after):
        return Reaction(
            {
                "ref_before_quote_id": None,
                "ref_asof_quote_id": None,
                "stock_return_pct": None,
                "benchmark_return_pct": None,
                "relative_return_pp": None,
                "missing_reason": "no_qualifying_quote",
            },
            None,
            detail={"version": cfg["version"]},
        )
    a, b = before[-1], after[-1]
    stock = _ret_pct(float(a.stock["mid"]), float(b.stock["mid"]))
    bench, missing = _basket_ret(a, b, w) if synced else (None, tuple(members))
    rel = None if bench is None else stock - bench

    mc = cfg["move_start"]
    lb = as_of - pd.Timedelta(minutes=int(mc["lookback_min"]))
    step = pd.Timedelta(seconds=int(mc["path_step_s"]))
    path = (
        sync_points(quotes, security, members, lb, as_of)
        if synced
        else _stock_only(quotes, security, lb, as_of)
    )
    sampled, nxt = [], None
    for p in path:
        if nxt is None or p.ts >= nxt:
            sampled.append(p)
            nxt = p.ts + step
    if path and sampled[-1].ts != path[-1].ts:
        sampled.append(path[-1])
    start, move_pp = move_start(sampled, w if synced else None, float(mc["min_move_pp"]))
    move_start_at = start if start is not None else a.ts

    rows = [_quote_row(a.stock, a.ts, vendor, rule_version), _quote_row(b.stock, b.ts, vendor, rule_version)]
    for p in (a, b):
        rows += [_quote_row(r, p.ts, vendor, rule_version) for r in p.constituents.values()]
    ids = (quote_id(security, a.ts), quote_id(security, b.ts))
    reaction = {
        "ref_before_quote_id": ids[0],
        "ref_asof_quote_id": ids[1],
        "stock_return_pct": round(stock, 6),
        "benchmark_return_pct": None if bench is None else round(bench, 6),
        "relative_return_pp": None if rel is None else round(rel, 6),
        "missing_reason": None if bench is not None else "benchmark_unavailable",
    }
    move = MarketMove(
        move_start_at.to_pydatetime(),
        ids[0],
        ids[1],
        stock,
        bench,
    )
    return Reaction(
        reaction,
        move,
        rows,
        {
            "version": cfg["version"],
            "missing_constituents": list(missing),
            "move_pp": round(move_pp, 6),
            "material_move": start is not None,
        },
    )


def persist_quotes(conn: Conn, rows: list[dict[str, Any]]) -> int:
    """Insert cited reference quotes (append-only; an existing quote id is left as it is)."""
    casts = {
        "session_type": "::session_type",
        "price_type": "::price_type",
        "quality_flags": "::quote_quality_flag[]",
    }
    n = 0
    for r in rows:
        cols = list(r)
        marks = ", ".join(f"%s{casts.get(c, '')}" for c in cols)
        cur = conn.execute(
            f"insert into reference_quotes ({', '.join(cols)}) values ({marks}) on conflict do nothing",
            [r[c] for c in cols],
        )
        n += cur.rowcount or 0
    return n


def window(analysis_as_of: datetime, anchor_at: datetime) -> tuple[datetime, datetime]:
    """The quote window compute_reaction reads: [min(anchor - ref lookback, as_of - move lookback), as_of]."""
    cfg = load("reaction")
    start = min(
        ensure_utc(anchor_at, "anchor_at") - timedelta(seconds=int(cfg["ref_before"]["max_lookback_s"])),
        ensure_utc(analysis_as_of, "as_of") - timedelta(minutes=int(cfg["move_start"]["lookback_min"])),
    )
    return start.to_pydatetime(), ensure_utc(analysis_as_of, "as_of").to_pydatetime()
