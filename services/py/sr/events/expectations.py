"""Expectation comparison (S2§3.3; DC §1.1 replay rule for expectation snapshots; AC-09).

A consensus snapshot qualifies only if it was taken BEFORE the disclosure (snapshot_as_of < source_published_at)
and was available by the analysis time. Day-precision snapshots qualify only when their date is strictly
earlier than the disclosure's ET date (a same-day snapshot cannot be proven to precede it).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sr.config import load
from sr.contracts._gen.expectation_snapshots_schema import ExpectationSnapshots
from sr.events.factcheck import CheckedFact
from sr.timeguard import ensure_utc

ET = ZoneInfo("America/New_York")
_COARSE = {"day", "unknown"}


def _dt(x: Any) -> datetime:
    """Generated pydantic models wrap timestamps in RootModel; unwrap to an aware datetime."""
    v = getattr(x, "root", x)
    assert isinstance(v, datetime)
    return v


def _basis_of(f: CheckedFact) -> str | None:
    if f.metric.endswith("_non_gaap"):
        return "non_gaap"
    if f.metric.endswith("_gaap"):
        return "gaap"
    return f.basis


def eligible(s: ExpectationSnapshots, disclosure_at: datetime, analysis_as_of: datetime) -> bool:
    if _dt(s.available_at) > analysis_as_of:
        return False
    if s.snapshot_precision.value in _COARSE:
        return _dt(s.snapshot_as_of).astimezone(ET).date() < disclosure_at.astimezone(ET).date()
    return _dt(s.snapshot_as_of) < disclosure_at


def compare(
    fact: CheckedFact,
    company_id: str,
    snapshots: list[dict[str, Any]],
    disclosure_at: datetime,
    analysis_as_of: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (expectation_comparison, missing_reason)."""
    cfg = load("earnings")["expectations"]
    disc = ensure_utc(disclosure_at, "disclosure_at").to_pydatetime()
    asof = ensure_utc(analysis_as_of, "analysis_as_of").to_pydatetime()
    snaps = [ExpectationSnapshots.model_validate(s) for s in snapshots]
    same = [
        s
        for s in snaps
        if s.company_id == company_id
        and s.metric == fact.metric
        and s.fiscal_period == fact.period
        and s.expectation_type.value in cfg["types"]
    ]
    pre = [s for s in same if eligible(s, disc, asof)]
    basis = _basis_of(fact)
    if cfg["require_same_basis"] and basis is not None:
        matched = [s for s in pre if s.accounting_basis.value == basis]
        if pre and not matched:
            return None, cfg["missing_reasons"]["basis"]
        pre = matched
    pre = [s for s in pre if s.value is not None]
    if not pre or fact.value is None:
        return None, cfg["missing_reasons"]["none"]
    s = max(pre, key=lambda x: (_dt(x.snapshot_as_of), _dt(x.available_at)))
    assert s.value is not None
    diff = fact.value - s.value
    out: dict[str, Any] = {
        "metric": fact.metric,
        "consensus_value": s.value,
        "consensus_as_of": _dt(s.snapshot_as_of).isoformat(),
        "consensus_exp_id": s.exp_id,
        "difference": diff,
        "comparison_basis": basis or s.accounting_basis.value,
    }
    if fact.unit == "pct":
        out["difference_pp"] = diff
    else:
        out["difference_pct"] = diff / abs(s.value) * 100 if s.value else None
    return out, None
