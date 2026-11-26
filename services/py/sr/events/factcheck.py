"""Deterministic checks on LLM-extracted facts (DP 1.07 确定性核对; D-32). The LLM proposes, code verifies:
1. canonical metric (aliases from config; EPS must state GAAP vs non-GAAP -> separate fields, AC-09)
2. the value equals a number printed in the fact's own quote, with a matching scale word — or, for a table row,
   the scale of the nearest table header above the quote in the document; losses/declines may be signed (OQ-39)
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
    r"(?P<neg>\()?(?P<cur>[A-Z]{2})?\$?\s?(?P<num>-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)\)?\s*"
    r"(?P<scale>billion|bn|b|million|mn|m|percent|%)?(?![a-z])",
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


def _numbers(quote: str, foreign: frozenset[str] = frozenset()) -> list[tuple[float, str]]:
    """(value, scale word) for each number; numbers printed with a foreign currency prefix are left out."""
    out = []
    for m in _NUM.finditer(quote):
        if m.group("cur") and m.group("cur").upper() in foreign:
            continue
        v = float(m.group("num").replace(",", ""))
        out.append((-v if m.group("neg") else v, (m.group("scale") or "").lower()))
    return out


def _quote_pos(text: str, quote: str, span: dict[str, int] | None) -> int:
    """Where the quote sits in the document: its span if that is exact, else the first occurrence (-1 if absent)."""
    if span:
        a, b = span.get("char_start"), span.get("char_end")
        if a is not None and b is not None and text[a:b] == quote:
            return int(a)
    return text.find(quote)


def header_scale_unit(text: str | None, quote: str, span: dict[str, int] | None) -> str | None:
    """Unit implied by the nearest table-header scale ("in millions", "($B)") above the quote, within the lookback."""
    if not text:
        return None
    pos = _quote_pos(text, quote, span)
    if pos < 0:
        return None
    hc = load("earnings")["checks"].get("document_header_scale")
    if not hc:
        return None
    window = text[max(0, pos - int(hc["lookback_chars"])) : pos + len(quote)]
    best: tuple[int, str] | None = None
    for p in hc["patterns"]:
        for m in re.finditer(p["regex"], window, re.IGNORECASE):
            if best is None or m.start() > best[0]:
                best = (m.start(), str(p["unit"]))
    return best[1] if best else None


def check_facts(
    facts: tuple[ExtractedFact, ...], default_period: str | None, text: str | None = None
) -> CheckReport:
    """`text` is the full document; without it only scale words inside the quote count (stricter)."""
    cfg = load("earnings")
    units, tol = cfg["units"], float(cfg["checks"]["value_tolerance"])
    lo, hi = cfg["checks"]["pct_range"]
    signed = set(cfg["checks"].get("signed_metrics", []))
    cues = [c.lower() for c in cfg["checks"].get("negative_cues", [])]
    foreign = frozenset(c.upper() for c in cfg["checks"].get("foreign_currency_prefixes", []))
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
        is_usd = str(u["unit"]).startswith("USD")
        if is_usd and f.currency and f.currency.upper() != "USD":
            rep.rejected.append(
                {"metric": name, "quote": f.quote, "reason": f"currency_not_supported:{f.currency}"}
            )
            continue
        if f.value is not None:
            scales = {s.lower() for s in u["scale"]}
            # the number must be printed in the quote with the scale word its unit implies (none for per-share/USD);
            # a table row may carry the scale once in its header, e.g. "Net income ($M) $2,428 …"
            markers = [m.lower() for m in cfg.get("quote_scale_markers", {}).get(f.unit, [])]
            header_scaled = any(m in f.quote.lower() for m in markers)
            if not header_scaled and scales and f.unit != "pct":
                header_scaled = header_scale_unit(text, f.quote, f.span) == f.unit
            # a loss or decline printed as a positive number next to a cue word ("operating loss was $134 million")
            targets = [f.value]
            if f.value < 0 and name in signed and any(c in f.quote.lower() for c in cues):
                targets.append(-f.value)
            ok = any(
                abs(v - t) <= tol
                and (((sc in scales) if scales else sc == "") or (header_scaled and sc == ""))
                for v, sc in _numbers(f.quote, foreign if is_usd else frozenset())
                for t in targets
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
