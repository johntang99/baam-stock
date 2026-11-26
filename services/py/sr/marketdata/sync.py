"""First synchronous qualifying quote search (D-06, D-07, D-10; DC §4).

A sync point is a sample second t where the target security has a qualifying quote and every basket
constituent (except at most `max_missing` of them) has a qualifying quote whose quote_ts is within
`tolerance_ms` of the target's quote_ts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

import pandas as pd

from sr.config import load
from sr.timeguard import LookaheadError, ensure_utc


@dataclass(frozen=True)
class SyncResult:
    status: Literal["ok", "no_sync"]
    sample_ts: pd.Timestamp | None = None
    quote: dict[str, object] | None = None                       # target row
    constituent_quotes: dict[str, dict[str, object]] = field(default_factory=dict)
    missing_constituents: tuple[str, ...] = ()
    invalid_reason: str | None = None                            # DC invalid_reason when no_sync
    detail: str = ""


def _cfg() -> dict[str, object]:
    return dict(load("quote_rules")["sync"])


def find_first_sync_qualifying(
    after_ts: datetime,
    security: str,
    basket: list[str],
    tolerance_ms: int = 2000,
    max_wait_s: int = 30,
    *,
    quotes: pd.DataFrame,
    max_missing: int | None = None,
    inclusive: bool = False,
    as_of: datetime | None = None,
    invalid_reason_if_none: str = "no_sync_start_quote",
) -> SyncResult:
    """Search (after_ts, after_ts + max_wait_s] (or [.., ..] if inclusive) for the first sync point.

    `quotes` must already be evaluated by quote_rules.evaluate_quotes. The target quote must itself be stamped
    after after_ts (quote_ts > after_ts; >= when inclusive) so that published_at < t0 quote_ts (AC-13).
    `as_of`: the time the search runs; quotes received after it are invisible, and a search window that is not
    over yet raises LookaheadError (the caller must wait, never peek).
    """
    t0 = ensure_utc(after_ts, "after_ts")
    end = t0 + timedelta(seconds=max_wait_s)
    mm = int(_cfg()["max_missing_constituents"]) if max_missing is None else max_missing
    if as_of is not None:
        cutoff = ensure_utc(as_of, "as_of")
        if end > cutoff:
            raise LookaheadError(f"sync window ends {end.isoformat()} after as_of {cutoff.isoformat()}")
        quotes = quotes[quotes["received_at"] <= cutoff]
    tol = pd.Timedelta(milliseconds=tolerance_ms)

    win = quotes[(quotes["ts"] >= t0) & (quotes["ts"] <= end) & quotes["is_qualifying"]]
    tgt = win[win["security_id"] == security]
    tgt = tgt[tgt["quote_ts"] >= t0] if inclusive else tgt[tgt["quote_ts"] > t0]
    if not inclusive:
        tgt = tgt[tgt["ts"] > t0]
    by_c = {c: g.set_index("ts") for c, g in win[win["security_id"].isin(basket)].groupby("security_id")}

    for _, row in tgt.sort_values("ts").iterrows():
        ts, qts = row["ts"], row["quote_ts"]
        got: dict[str, dict[str, object]] = {}
        missing = []
        for c in basket:
            g = by_c.get(c)
            if g is not None and ts in g.index:
                cr = g.loc[ts]
                if abs(cr["quote_ts"] - qts) <= tol:
                    got[c] = cr.to_dict() | {"ts": ts, "security_id": c}
                    continue
            missing.append(c)
        if len(missing) <= mm:
            return SyncResult("ok", ts, row.to_dict(), got, tuple(missing),
                              detail=f"{len(got)}/{len(basket)} constituents within {tolerance_ms}ms")
    return SyncResult("no_sync", invalid_reason=invalid_reason_if_none,
                      detail=f"no sync point in window ending {end.isoformat()} (max_missing={mm})")
