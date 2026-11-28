"""Corporate actions (DP 1.21; AC-37; D-40; DC corporate_actions / security_identifiers; OQ-56).

- record_action(): stores an action (ticker change -> closes the open ticker row at ex_date, adds the new one).
- resolve_ticker(): which security a ticker meant on a given date (old codes keep resolving at their own dates).
- actions_crossing(): actions available by `as_of` that fall inside a forecast window.
- adjust_start(): the start price restated in post-action terms, or an invalid reason (`corporate_action`).
- back_adjust(): research-library adjusted prices; reference_quotes always keep the raw price.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from sr.calendar import get_calendar
from sr.config import load
from sr.db import Conn
from sr.ids import new_id
from sr.timeguard import ensure_utc


def record_action(conn: Conn, action: dict[str, Any], new_ticker: str | None = None) -> str:
    """Insert one action. A ticker_change needs `new_ticker` and updates security_identifiers (rule ④)."""
    if action["action_type"] == "ticker_change" and not new_ticker:
        raise ValueError("a ticker_change needs new_ticker")
    aid = action.get("action_id") or new_id("ca")
    cols = [
        "action_id",
        "security_id",
        "action_type",
        "announced_at",
        "ex_date",
        "effective_at",
        "ratio",
        "cash_amount",
        "source_id",
        "available_at",
    ]
    row = {**{c: action.get(c) for c in cols}, "action_id": aid}
    conn.execute(
        f"insert into corporate_actions ({', '.join(cols)}) values ({', '.join('%s::corporate_action_type' if c == 'action_type' else '%s' for c in cols)})",
        [row[c] for c in cols],
    )
    if action["action_type"] == "ticker_change":
        ex = action["ex_date"]
        conn.execute(
            """update security_identifiers set valid_to = %s
                where security_id = %s and id_type = 'ticker' and valid_to is null and valid_from < %s""",
            (ex, action["security_id"], ex),
        )
        conn.execute(
            "insert into security_identifiers (security_id, id_type, value, valid_from) values (%s, 'ticker', %s, %s)",
            (action["security_id"], new_ticker, ex),
        )
    return str(aid)


def resolve_ticker(conn: Conn, ticker: str, on: date) -> str | None:
    row = conn.execute(
        """select security_id from security_identifiers
            where id_type = 'ticker' and value = %s and valid_from <= %s and (valid_to is null or %s < valid_to)""",
        (ticker, on, on),
    ).fetchone()
    return None if row is None else str(row["security_id"])


def actions_crossing(
    conn: Conn, security_ids: list[str], start: datetime, end: datetime, as_of: datetime
) -> list[dict[str, Any]]:
    """Actions known by as_of with ex_date in (start session, end session] or effective_at in (start, end]."""
    cal = get_calendar()
    d0 = cal.session_for_instant(ensure_utc(start, "start").to_pydatetime()).session_date
    d1 = cal.session_for_instant(ensure_utc(end, "end").to_pydatetime()).session_date
    rows = conn.execute(
        """select * from corporate_actions
            where security_id = any(%s) and available_at <= %s
              and ((ex_date > %s and ex_date <= %s) or (effective_at > %s and effective_at <= %s))
            order by ex_date""",
        (
            security_ids,
            ensure_utc(as_of, "as_of").to_pydatetime(),
            d0,
            d1,
            ensure_utc(start, "start").to_pydatetime(),
            ensure_utc(end, "end").to_pydatetime(),
        ),
    ).fetchall()
    return [dict(r) for r in rows]


@dataclass(frozen=True)
class Adjusted:
    price: float | None  # None -> invalid
    invalid_reason: str | None
    applied: tuple[str, ...] = ()  # action ids used


def adjust_start(start_price: float, actions: list[dict[str, Any]], prev_close: float | None) -> Adjusted:
    cfg = load("corporate_actions")
    p, used = float(start_price), []
    for a in actions:
        t = a["action_type"]
        if t == "ticker_change":
            continue  # no price effect
        if t in cfg["ratio_types"]:
            if a["ratio"] is None:
                return Adjusted(None, "corporate_action")
            p /= float(a["ratio"])
        elif t in cfg["cash_types"]:
            if a["cash_amount"] is None:
                return Adjusted(None, "corporate_action")
            base = prev_close or start_price
            if float(a["cash_amount"]) / float(base) * 100.0 < float(cfg["dividend_ignore_below_pct"]):
                continue  # D-40: too small to matter
            p -= float(a["cash_amount"])
        else:  # spin_off / merger_delisting: no usable ratio in Phase 1
            return Adjusted(None, "corporate_action")
        used.append(str(a["action_id"]))
    return Adjusted(p, None, tuple(used))


def back_adjust(
    prices: pd.Series, actions: list[dict[str, Any]], prev_closes: dict[date, float] | None = None
) -> pd.Series:
    """Research-library adjusted prices: values before each ex_date scaled into post-action terms. `prices` is
    indexed by session date (or timestamps whose ET date is the session)."""
    cfg = load("corporate_actions")
    out = prices.astype(float).copy()
    idx = pd.Index([d.date() if hasattr(d, "date") and not isinstance(d, date) else d for d in out.index])
    for a in actions:
        t, ex = a["action_type"], a["ex_date"]
        before = idx < ex
        if t in cfg["ratio_types"] and a["ratio"] is not None:
            out[before] = out[before] / float(a["ratio"])
        elif t in cfg["cash_types"] and a["cash_amount"] is not None:
            prev = (prev_closes or {}).get(ex)
            if prev is None:
                prior = out[before]
                prev = float(prior.iloc[-1]) if len(prior) else None
            if prev and float(a["cash_amount"]) / prev * 100.0 >= float(cfg["dividend_ignore_below_pct"]):
                out[before] = out[before] * (1.0 - float(a["cash_amount"]) / prev)
    return out
