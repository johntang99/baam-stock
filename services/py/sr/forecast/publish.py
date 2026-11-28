"""Atomic publish + t0 attachment (DP 1.14; DC §3.7, §4; AC-13; OQ-48).

publish(): every prediction_runs row and its predictions are written in ONE transaction with their final status
(`published` or `abstained`) — there is no window in which a half-published forecast exists. The idempotency key
(security + snapshot + target + model) makes a retry return the rows already written.

attach_t0(): after publishing, the first sync qualifying quote strictly after published_at becomes t0 (D-05,
D-06): t0_quote_id / t0_benchmark_quote_ids / target_end_at are set and the status moves to awaiting_settlement.
Probabilities, quantiles, thresholds, locked and published_at are frozen by the DB trigger and never touched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sr.config import load
from sr.db import Conn, jsonb
from sr.events.reaction import persist_quotes, quote_id, quote_row
from sr.marketdata.sync import find_first_sync_qualifying
from sr.timeguard import ensure_utc

RUN_JSON: tuple[str, ...] = ()
PRED_JSON = ("probabilities", "interval", "move_quantiles", "scenarios", "locked")
PRED_CASTS = {
    "status": "::prediction_status",
    "display_tier": "::display_tier",
    "abstain_reason": "::abstain_reason",
    "sampling_rule": "::sampling_rule",
}


@dataclass(frozen=True)
class Published:
    run_ids: list[str]
    prediction_ids: list[str]
    reused: bool


def publish(conn: Conn, runs: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> Published:
    keys = [r["idempotency_key"] for r in runs]
    have = conn.execute(
        "select run_id from prediction_runs where idempotency_key = any(%s)", (keys,)
    ).fetchall()
    if have:
        if len(have) != len(runs):
            raise RuntimeError("partial earlier publish found for these idempotency keys")
        ids = [h["run_id"] for h in have]
        preds = conn.execute(
            "select prediction_id from predictions where run_id = any(%s) order by prediction_id", (ids,)
        ).fetchall()
        return Published(ids, [p["prediction_id"] for p in preds], True)
    with conn.transaction():
        for r in runs:
            cols = list(r)
            marks = ", ".join(f"%s{'::trigger_type' if c == 'trigger_type' else ''}" for c in cols)
            conn.execute(
                f"insert into prediction_runs ({', '.join(cols)}) values ({marks})", [r[c] for c in cols]
            )
        for p in predictions:
            cols = list(p)
            marks = ", ".join(f"%s{PRED_CASTS.get(c, '')}" for c in cols)
            conn.execute(
                f"insert into predictions ({', '.join(cols)}) values ({marks})",
                [jsonb(p[c]) if c in PRED_JSON and p[c] is not None else p[c] for c in cols],
            )
    return Published([r["run_id"] for r in runs], [p["prediction_id"] for p in predictions], False)


@dataclass(frozen=True)
class T0:
    status: str  # attached | no_sync | not_published
    t0_quote_id: str | None = None
    target_end_at: datetime | None = None
    detail: str = ""


def attach_t0(
    conn: Conn,
    prediction_id: str,
    quotes: pd.DataFrame,
    weights: dict[str, float],
    as_of: datetime,
    vendor_source_id: str | None = None,
) -> T0:
    """`quotes`: evaluated 1-second quotes received by `as_of` (stock + basket)."""
    p = conn.execute("select * from predictions where prediction_id = %s", (prediction_id,)).fetchone()
    if p is None:
        raise KeyError(prediction_id)
    if p["status"] != "published" or p["published_at"] is None:
        return T0("not_published", detail=str(p["status"]))
    sync = load("quote_rules")["sync"]
    r = find_first_sync_qualifying(
        p["published_at"],
        p["security_id"],
        list(weights),
        int(sync["tolerance_ms"]),
        int(sync["start_max_wait_s"]),
        quotes=quotes,
        as_of=as_of,
    )
    if r.status != "ok" or r.sample_ts is None or r.quote is None:
        return T0("no_sync", detail=r.detail)  # settlement (1.15) records no_sync_start_quote
    t0_quote_ts = ensure_utc(r.quote["quote_ts"], "quote_ts")
    if not t0_quote_ts > ensure_utc(p["published_at"], "published_at"):  # AC-13: published_at < t0 quote_ts
        raise AssertionError("t0 quote is not after published_at")
    rule = load("quote_rules")["quote_rule_version"]
    vendor = vendor_source_id or str(load("reaction")["vendor_source_id"])
    rows = [quote_row(r.quote, r.sample_ts, vendor, rule)] + [
        quote_row(c, r.sample_ts, vendor, rule) for c in r.constituent_quotes.values()
    ]
    persist_quotes(conn, rows)
    dur = next(t for t in load("targets")["targets"] if t["target_row_id"] == p["target_row_id"])[
        "window_rule"
    ]["duration_min"]
    end = (r.sample_ts + timedelta(minutes=int(dur))).to_pydatetime()
    qid = quote_id(p["security_id"], r.sample_ts)
    conn.execute(
        """update predictions set t0_quote_id = %s, t0_benchmark_quote_ids = %s, target_end_at = %s, valid_until = %s,
                  status = 'awaiting_settlement' where prediction_id = %s""",
        (qid, sorted(quote_id(c, r.sample_ts) for c in r.constituent_quotes), end, end, prediction_id),
    )
    return T0("attached", qid, end)
