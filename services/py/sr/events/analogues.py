"""Historical analogues hc-0.1 (DP 1.22; D-38; DC §3.4a; AC-38).

Rules:
1. Only the past: a case counts only if both its availability and its outcome settlement are <= analysis_as_of.
   The same event chain (same event / identity key) never matches itself.
2. Match keys: event_type + subtype + industry_template + market_state (+ surprise_bucket for earnings).
3. Statistic: the case's relative-to-basket return (pp) for the same target window -> median, IQR, share > 0.
4. min_cases (8): relax drop_subtype -> peer_group -> sector_wide, recording the level; still short ->
   insufficient=true and no median (the UI then shows "历史样本不足").
5. Reference only: n, period and fallback level always travel with the numbers; never a direction signal.
6. Replay: deterministic, case_ids sorted and locked into the analysis version.

Case outcomes come from published analysis versions whose `market_reaction` carries `outcomes` (pp per target),
`market_state` and `settled_at` — written by the market-reaction step (DP 1.09), see OQ-36.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from sr.config import load
from sr.db import Conn
from sr.timeguard import ensure_utc


@dataclass(frozen=True)
class AnalogueCase:
    case_id: str  # analysis_id of the case's analysis version
    event_id: str
    chain_key: str  # events.identity_key (re-publications / revisions share it)
    company_id: str
    industry_template: str
    sector: str
    event_type: str
    subtype: str | None
    market_state: str | None
    surprise_bucket: str | None
    available_at: datetime  # when the case (event + analysis) was available
    settled_at: datetime  # when its outcome was known
    outcomes: dict[str, float] = field(default_factory=dict)  # target_id -> relative return pp
    template_retroactive: bool = False  # industry template taken from a later profile (OQ-36)


@dataclass(frozen=True)
class AnalogueQuery:
    event_id: str
    chain_key: str
    company_id: str
    industry_template: str
    sector: str
    event_type: str
    subtype: str | None
    market_state: str | None
    surprise_bucket: str | None
    target_id: str
    analysis_as_of: datetime


def surprise_bucket(expectation_comparison: dict[str, Any] | None) -> str | None:
    """below / in_line / above from the headline comparison; None when there was no pre-event consensus."""
    if not expectation_comparison:
        return None
    cfg = load("analogues/hc-0.1")["surprise_buckets"]
    if expectation_comparison.get("difference_pp") is not None:
        d, tol = float(expectation_comparison["difference_pp"]), float(cfg["pp_tolerance"])
    elif expectation_comparison.get("difference_pct") is not None:
        d, tol = float(expectation_comparison["difference_pct"]), float(cfg["pct_tolerance"])
    else:
        return None
    return "in_line" if abs(d) <= tol else ("above" if d > 0 else "below")


def _eligible(c: AnalogueCase, q: AnalogueQuery, asof: datetime) -> bool:
    return (
        c.available_at <= asof
        and c.settled_at <= asof
        and c.event_id != q.event_id
        and c.chain_key != q.chain_key
        and q.target_id in c.outcomes
    )


def _matches(c: AnalogueCase, q: AnalogueQuery, keys: list[str], companies: str, earnings_type: str) -> bool:
    if companies == "same_company" and c.company_id != q.company_id:
        return False
    if companies == "same_template" and c.industry_template != q.industry_template:
        return False
    if companies == "same_sector" and c.sector != q.sector:
        return False
    for k in keys:
        if k == "surprise_bucket" and q.event_type != earnings_type:
            continue
        if getattr(c, k) != getattr(q, k):
            return False
    return True


def find_analogues(q: AnalogueQuery, cases: list[AnalogueCase]) -> dict[str, Any]:
    cfg = load("analogues/hc-0.1")
    asof = ensure_utc(q.analysis_as_of, "analysis_as_of").to_pydatetime()
    pool = [c for c in cases if _eligible(c, q, asof)]
    match_keys = {
        "event_type": q.event_type,
        "subtype": q.subtype,
        "industry_template": q.industry_template,
        "market_state": q.market_state,
    }
    if q.event_type == cfg["earnings_event_type"]:
        match_keys["surprise_bucket"] = q.surprise_bucket
    chosen: list[AnalogueCase] = []
    level = cfg["levels"][-1]["name"]
    for lv in cfg["levels"]:
        chosen = [c for c in pool if _matches(c, q, lv["keys"], lv["companies"], cfg["earnings_event_type"])]
        level = lv["name"]
        if len(chosen) >= int(cfg["min_cases"]):
            break
    chosen.sort(key=lambda c: (c.available_at, c.case_id))
    insufficient = len(chosen) < int(cfg["min_cases"])
    out: dict[str, Any] = {
        "query_version": cfg["query_version"],
        "match_keys": match_keys,
        "target_id": q.target_id,
        "n": len(chosen),
        "period": (
            {"start": chosen[0].available_at.isoformat(), "end": chosen[-1].available_at.isoformat()}
            if chosen
            else None
        ),
        "case_ids": sorted(c.case_id for c in chosen),
        "fallback_applied": level != "none",
        "fallback_level": level,
        "insufficient": insufficient,
        "median_relative_pp": None,
        "iqr_pp": None,
        "hit_share_positive": None,
    }
    if not insufficient:
        v = np.array([c.outcomes[q.target_id] for c in chosen], dtype=float)
        q25, q50, q75 = np.percentile(v, [25, 50, 75])
        out.update(
            median_relative_pp=float(q50), iqr_pp=float(q75 - q25), hit_share_positive=float(np.mean(v > 0))
        )
    return out


def load_cases(conn: Conn, analysis_as_of: datetime) -> list[AnalogueCase]:
    """Point-in-time case library: latest analysis version per (event, security) published by as_of that carries
    settled outcomes. Anything published or settled later is not returned."""
    asof = ensure_utc(analysis_as_of, "analysis_as_of").to_pydatetime()
    rows = conn.execute(
        """select distinct on (a.event_id, a.security_id) a.analysis_id, a.event_id, a.published_at, a.market_reaction,
                  a.expectation_comparison, e.identity_key, e.category, e.subtype, s.company_id, c.sector,
                  coalesce(p.industry_template::text, 'generic') as industry_template,
                  coalesce(p.retroactive, false) as template_retroactive
           from event_analysis_versions a
           join events e using (event_id)
           join securities s on s.security_id = a.security_id
           join companies c on c.company_id = s.company_id
           left join lateral (select industry_template, pv.effective_from > %(t)s as retroactive
                              from company_profile_versions pv where pv.company_id = s.company_id
                              -- in-effect profile first; else the earliest one, applied retroactively (OQ-08/OQ-36)
                              order by (pv.effective_from <= %(t)s) desc,
                                       case when pv.effective_from <= %(t)s then -pv.version else pv.version end
                              limit 1) p on true
           where a.published_at <= %(t)s
           order by a.event_id, a.security_id, a.analysis_version desc""",
        {"t": asof},
    ).fetchall()
    out: list[AnalogueCase] = []
    for r in rows:
        mr = r["market_reaction"] or {}
        outcomes = mr.get("outcomes") or {}
        settled = mr.get("settled_at")
        if not outcomes or not settled:
            continue
        settled_at = ensure_utc(datetime.fromisoformat(settled), "settled_at").to_pydatetime()
        if settled_at > asof:
            continue
        out.append(
            AnalogueCase(
                case_id=r["analysis_id"],
                event_id=r["event_id"],
                chain_key=r["identity_key"],
                company_id=r["company_id"],
                industry_template=r["industry_template"],
                sector=r["sector"],
                event_type=r["category"],
                subtype=r["subtype"],
                market_state=mr.get("market_state"),
                surprise_bucket=surprise_bucket(r["expectation_comparison"]),
                available_at=r["published_at"],
                settled_at=settled_at,
                outcomes={k: float(v) for k, v in outcomes.items() if v is not None},
                template_retroactive=bool(r["template_retroactive"]),
            )
        )
    return out
