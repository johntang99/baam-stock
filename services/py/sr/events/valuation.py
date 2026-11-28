"""Valuation background for explanations (DP 1.24; AC-42; DC market_explanation.valuation_context; D-16; OQ-54).

valuation_context() turns a valuation source into `{as_of, fwd_pe, fwd_pe_pctile_3y, peer_median_fwd_pe,
ev_sales_ntm?, source_id, note}`, reading only values available by the analysis time. Without a licensed source
(D-16 pending) there is no context at all and the page hides the row.

It is background only: check_feature_inputs() raises ExplanationOnlyField whenever model features ask for any
valuation field, so it can never reach a short-term model.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any, Protocol

import pandas as pd

from sr.config import load
from sr.db import Conn
from sr.timeguard import ensure_utc

COLUMNS = ["security_id", "as_of", "fwd_pe", "ev_sales_ntm", "available_at"]


class ExplanationOnlyField(RuntimeError):
    """A field meant for explanations only (e.g. valuation) was requested as a model feature (AC-42)."""


def check_feature_inputs(names: Iterable[str]) -> None:
    banned = set(load("valuation")["explanation_only_fields"])
    hit = sorted({n for n in names for b in banned if n == b or n == f"f_{b}" or n.endswith(f".{b}")})
    if hit:
        raise ExplanationOnlyField(f"explanation-only fields cannot be model features: {hit}")


class ValuationSource(Protocol):
    source_id: str

    def points(self, security_ids: list[str], start: datetime, end: datetime) -> pd.DataFrame: ...


class NoValuationSource:
    """The default until a licensed source exists (D-16): no values, so no valuation context."""

    source_id = "none"

    def points(self, security_ids: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        return pd.DataFrame(columns=COLUMNS)


class FrameValuationSource:
    """In-memory values (tests / synthetic fixtures)."""

    def __init__(self, df: pd.DataFrame, source_id: str = "src_valuation_synthetic") -> None:
        self.df, self.source_id = df, source_id

    def points(self, security_ids: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        d = self.df
        return d[
            d["security_id"].isin(security_ids)
            & (d["as_of"] >= pd.Timestamp(start))
            & (d["as_of"] <= pd.Timestamp(end))
        ]


def peers_for(conn: Conn, security_id: str, at: datetime) -> list[str]:
    """company_profile_versions.valuation_peers in force at `at`, else the benchmark basket constituents."""
    row = conn.execute(
        """select p.valuation_peers from company_profile_versions p join securities s on s.company_id = p.company_id
            where s.security_id = %s and p.effective_from <= %s order by p.version desc limit 1""",
        (security_id, ensure_utc(at, "at").to_pydatetime()),
    ).fetchone()
    if row and row["valuation_peers"]:
        return [p if p.startswith("sec_") else f"sec_{p.lower()}" for p in row["valuation_peers"]]
    from sr.snapshot.builder import benchmark_version

    _, w = benchmark_version(conn, security_id, ensure_utc(at, "at").date())
    return list(w)


def valuation_context(
    source: ValuationSource, security_id: str, peers: list[str], as_of: datetime
) -> dict[str, Any] | None:
    cfg = load("valuation")
    t = ensure_utc(as_of, "as_of")
    start = t - timedelta(days=365 * int(cfg["lookback_years"]))
    raw = source.points([security_id, *peers], start.to_pydatetime(), t.to_pydatetime())
    if raw is None or raw.empty:
        return None
    d = raw.copy()
    d["as_of"] = pd.to_datetime(d["as_of"], utc=True)
    d["available_at"] = pd.to_datetime(d["available_at"], utc=True)
    d = d[(d["available_at"] <= t) & (d["as_of"] <= t) & d["fwd_pe"].notna()]  # what was known at the time
    own = d[d["security_id"] == security_id].sort_values("as_of")
    if own.empty:
        return None
    cur = own.iloc[-1]
    pct = None
    if len(own) >= int(cfg["min_history_points"]):
        pct = round(float((own["fwd_pe"] <= cur["fwd_pe"]).mean() * 100.0), 1)
    fresh = d[
        (d["security_id"].isin(peers)) & (d["as_of"] >= t - pd.Timedelta(days=int(cfg["peer_max_age_days"])))
    ]
    latest = fresh.sort_values("as_of").groupby("security_id")["fwd_pe"].last()
    peer_median = round(float(latest.median()), 2) if len(latest) >= int(cfg["peer_min"]) else None
    fwd_pe = round(float(cur["fwd_pe"]), 2)
    parts = [f"远期市盈率 {fwd_pe:.1f}"]
    if pct is not None:
        parts.append(f"处于近 3 年 {pct:.0f} 分位")
    if peer_median is not None:
        parts.append(f"同行中位数 {peer_median:.1f}")
    out: dict[str, Any] = {
        "as_of": cur["as_of"].isoformat(),
        "fwd_pe": fwd_pe,
        "fwd_pe_pctile_3y": pct,
        "peer_median_fwd_pe": peer_median,
        "source_id": source.source_id,
        "note": "，".join(parts) + "（只作背景，不进入短线模型）",
    }
    if "ev_sales_ntm" in cur and pd.notna(cur["ev_sales_ntm"]):
        out["ev_sales_ntm"] = round(float(cur["ev_sales_ntm"]), 2)
    return out
