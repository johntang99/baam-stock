"""Deterministic checks on LLM-extracted facts (DP 1.07 确定性核对; D-32). The LLM proposes, code verifies:
1. canonical metric (aliases from config; EPS must state GAAP vs non-GAAP -> separate fields, AC-09)
2. the value equals a number printed in the fact's own quote, with a matching scale word
3. unit normalisation (USD billions -> USD) and range checks (percentages)
4. conflicts: the same metric/basis/period with different values in one document -> both withheld for review
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sr.config import load
from sr.llm.base import ExtractedFact

_NUM = re.compile(
    r"(?P<neg>\()?\$?\s?(?P<num>-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)\)?\s*"
    r"(?P<scale>billion|bn|million|mn|percent|%)?(?![a-z])",
    re.IGNORECASE,
)
_PERIOD = [  # quarters, in the company's own fiscal labelling ("third quarter of 2026" -> FY2026Q3)
    re.compile(r"FY\s?(?P<y>\d{4})\s?Q(?P<q>[1-4])", re.I),
    re.compile(r"Q(?P<q>[1-4])\s*(?:of\s*)?(?:FY|fiscal(?:\s+year)?)?\s*'?(?P<y>\d{4})", re.I),
    re.compile(
        r"(?P<word>first|second|third|fourth)\s+(?:fiscal\s+)?quarter\s+(?:of\s+)?(?:fiscal\s+)?(?:year\s+)?(?P<y>\d{4})",
        re.I,
    ),
]
_ANNUAL = re.compile(
    r"^\s*(?:FY\s?|fiscal\s+(?:year\s+)?|full[- ]year\s+(?:fiscal\s+)?)(?P<y>\d{4})\s*$", re.I
)
_WORDQ = {"first": 1, "second": 2, "third": 3, "fourth": 4}


@dataclass(frozen=True)
class CheckedFact:
    metric: str  # canonical, e.g. eps_non_gaap
    value: float | None  # normalised (USD, pct, USD_per_share)
    unit: str
    currency: str | None
    period: str | None
    basis: str | None
    quote: str
    span: dict[str, int]
    raw_value: float | None
    raw_unit: str
    direction: str | None = None
    scope: str | None = None
    certainty: str | None = None
    metric_label: str | None = None
    segment: str | None = None


@dataclass
class CheckReport:
    accepted: list[CheckedFact] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)  # {metric, quote, reason}

    @property
    def gaps(self) -> list[str]:
        return [f"fact_check_failed:{r['metric']}:{r['reason']}" for r in self.rejected]


def _key(s: str) -> str:
    return re.sub(r"[\s_]+", " ", s.strip().lower())


def canonical_metric(metric: str, basis: str | None) -> tuple[str | None, str]:
    cfg = load("earnings")["metrics"]
    k = _key(metric)
    for name, m in cfg.items():
        if k == _key(name) or k in {_key(a) for a in m["aliases"]}:
            if m.get("basis_in_name"):
                if basis not in ("gaap", "non_gaap"):
                    return None, "basis_not_stated"
                return f"{name}_{basis}", ""
            return name, ""
    if k in ("eps gaap", "eps non gaap", "eps_gaap", "eps_non_gaap"):
        return k.replace(" ", "_"), ""
    return None, "unknown_metric"


def normalize_period(period: str | None) -> str | None:
    if not period:
        return None
    for rx in _PERIOD:
        m = rx.search(period)
        if m:
            q = (
                _WORDQ[m.group("word").lower()]
                if "word" in m.groupdict() and m.group("word")
                else int(m.group("q"))
            )
            return f"FY{m.group('y')}Q{q}"
    m2 = _ANNUAL.match(period)
    return f"FY{m2.group('y')}" if m2 else None


def _numbers(quote: str) -> list[tuple[float, str]]:
    out = []
    for m in _NUM.finditer(quote):
        v = float(m.group("num").replace(",", ""))
        out.append((-v if m.group("neg") else v, (m.group("scale") or "").lower()))
    return out


def check_facts(facts: tuple[ExtractedFact, ...], default_period: str | None) -> CheckReport:
    cfg = load("earnings")
    units, tol = cfg["units"], float(cfg["checks"]["value_tolerance"])
    lo, hi = cfg["checks"]["pct_range"]
    rep = CheckReport()
    seen: dict[tuple[str, str | None, str | None, str | None], CheckedFact] = {}
    conflicts: set[tuple[str, str | None, str | None, str | None]] = set()
    for f in facts:
        name, why = canonical_metric(f.metric, f.basis)
        if name is None:
            rep.rejected.append({"metric": f.metric, "quote": f.quote, "reason": why})
            continue
        if f.unit not in units:
            rep.rejected.append({"metric": name, "quote": f.quote, "reason": f"unit_not_allowed:{f.unit}"})
            continue
        u = units[f.unit]
        if f.value is not None:
            scales = {s.lower() for s in u["scale"]}
            # the number must be printed in the quote with the scale word its unit implies (none for per-share/USD);
            # a table row may carry the scale once in its header, e.g. "Net income ($M) $2,428 …"
            markers = [m.lower() for m in cfg.get("quote_scale_markers", {}).get(f.unit, [])]
            header_scaled = any(m in f.quote.lower() for m in markers)
            ok = any(
                abs(v - f.value) <= tol
                and ((sc in scales) if scales else sc == "")
                or (abs(v - f.value) <= tol and header_scaled and sc == "")
                for v, sc in _numbers(f.quote)
            )
            if not ok:
                rep.rejected.append({"metric": name, "quote": f.quote, "reason": "value_not_in_quote"})
                continue
            plo, phi = cfg["checks"].get("pct_range_by_metric", {}).get(name, (lo, hi))
            if u["unit"] == "pct" and not plo <= f.value <= phi:
                rep.rejected.append({"metric": name, "quote": f.quote, "reason": "pct_out_of_range"})
                continue
        value = (
            None if f.value is None else round(f.value * float(u["mult"]), 6)
        )  # no float artefacts (33.2e9)
        period = normalize_period(f.period) or default_period
        cf = CheckedFact(
            name,
            value,
            u["unit"],
            f.currency or ("USD" if u["unit"].startswith("USD") else None),
            period,
            f.basis,
            f.quote,
            f.span,
            f.value,
            f.unit,
            direction=f.direction,
            scope=f.scope,
            certainty=f.certainty,
            metric_label=f.metric_label,
            segment=f.segment,
        )
        segment = (f.segment or "").strip().lower() or None
        key = (name, f.basis if not name.startswith("eps_") else None, period, segment)
        if key in seen and seen[key].value != cf.value:
            conflicts.add(key)
        seen.setdefault(key, cf)
    for key, cf in seen.items():
        if key in conflicts:
            rep.rejected.append({"metric": cf.metric, "quote": cf.quote, "reason": "conflicting_values"})
        else:
            rep.accepted.append(cf)
    return rep
