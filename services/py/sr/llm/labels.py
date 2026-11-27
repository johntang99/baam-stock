"""Gold labels for the extraction evaluation set (DP 1.18; D-32). One JSON file per document under
<labels>/labels/<doc key>.json. Only `label_status: reviewed` files count; drafts (pre-labels) never do."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from sr.config import load, repo_root


class GoldFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str  # canonical (sr.events.factcheck), e.g. revenue, eps_non_gaap
    value: float | None  # normalised units (USD, pct, USD_per_share)
    unit: str
    period: str | None = None  # FY2027Q3 …
    basis: Literal["gaap", "non_gaap", "company_defined"] | None = None
    quote: str
    direction: Literal["increase", "decrease", "unchanged", "none"] = "none"
    scope: Literal["company", "segment", "product", "geography", "other"] = "company"
    certainty: Literal["reported", "guidance", "expectation", "hypothetical"] = "reported"
    segment: str | None = None  # None = company-wide figure


class DocLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_key: str  # manifest key, e.g. 0001045810-24-000123:ex991.htm
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")  # sha of the normalised text the labels refer to
    doc_kind: Literal["earnings_release", "8k_other", "periodic_report", "policy", "news"]
    fiscal_period: str | None = None
    label_status: Literal["draft", "reviewed"]
    labeled_by: str
    facts: list[GoldFact]


def labels_dir(root: Path | None = None) -> Path:
    return root or repo_root() / load("extraction_eval")["paths"]["labels"]


def safe_key(doc_key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", doc_key)


def write_label(label: DocLabel, root: Path | None = None) -> Path:
    d = labels_dir(root) / "labels"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{safe_key(label.doc_key)}.json"
    p.write_text(json.dumps(label.model_dump(), ensure_ascii=False, indent=2) + "\n")
    return p


def read_labels(root: Path | None = None, reviewed_only: bool = True) -> list[DocLabel]:
    d = labels_dir(root) / "labels"
    out = (
        [DocLabel.model_validate_json(p.read_text()) for p in sorted(d.glob("*.json"))] if d.exists() else []
    )
    return [x for x in out if x.label_status == "reviewed"] if reviewed_only else out


def read_manifest(root: Path | None = None) -> dict[str, dict[str, object]]:
    p = labels_dir(root) / "manifest.jsonl"
    if not p.exists():
        return {}
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return {str(r["doc_key"]): r for r in rows}


def stratified(manifest: dict[str, dict[str, Any]], keys: list[str]) -> list[str]:
    """Round-robin over (ticker, file kind) groups, newest first; press-release exhibits lead each round."""
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for k in keys:
        r = manifest[k]
        groups[(str(r["ticker"]), str(r["file_kind"]))].append(k)
    for members in groups.values():
        members.sort(key=lambda k: (str(manifest[k]["filing_date"]), k), reverse=True)
    order = sorted(groups, key=lambda g: (g[1] != "ex99", g[0]))
    out: list[str] = []
    while any(groups[g] for g in order):
        for g in order:
            if groups[g]:
                out.append(groups[g].pop(0))
    return out


# --- label lint (reviewer self-check; docs/labeling/extraction-v0.md) ---
GOLD_UNITS = ("USD", "pct", "USD_per_share")
_PERIOD_RX = re.compile(r"^FY\d{4}(Q[1-4])?$")
_NUMS = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SCALES = (1.0, 1e3, 1e6, 1e9, 1e12)


@dataclass(frozen=True)
class LabelIssue:
    level: Literal["error", "warning"]
    fact: int | None  # index in facts, None = the whole file
    message: str


def gold_metrics() -> list[str]:
    out = []
    for name, m in load("earnings")["metrics"].items():
        out += [f"{name}_gaap", f"{name}_non_gaap"] if m.get("basis_in_name") else [name]
    return out


def _value_printed(value: float, quote: str) -> bool:
    nums = [float(x.replace(",", "")) for x in _NUMS.findall(quote) if x.replace(",", "").replace(".", "")]
    return any(abs(abs(value) - n * s) <= 1e-6 * max(1.0, abs(value)) for n in nums for s in _SCALES)


def lint_label(label: DocLabel, text: str | None, file_name: str | None = None) -> list[LabelIssue]:
    """Mechanical checks a reviewer can run before submitting. Errors would break or skew the evaluation;
    warnings are worth a second look."""
    from sr.evidence.hashing import sha256_text

    out: list[LabelIssue] = []
    if file_name is not None and file_name != f"{safe_key(label.doc_key)}.json":
        out.append(LabelIssue("error", None, f"file name should be {safe_key(label.doc_key)}.json"))
    if text is None:
        out.append(LabelIssue("error", None, "source document not found locally (run fetch_sec_corpus.py)"))
    elif sha256_text(text) != label.text_sha256:
        out.append(LabelIssue("error", None, "text_sha256 does not match the document: do not edit it"))
    if label.label_status == "reviewed" and (
        not label.labeled_by.strip() or label.labeled_by.startswith("prelabel:")
    ):
        out.append(LabelIssue("error", None, "reviewed files need labeled_by = the reviewer's name"))
    metrics = set(gold_metrics())
    seen: dict[tuple[str, str | None, str | None, str | None], int] = {}
    for i, f in enumerate(label.facts):
        if f.metric not in metrics:
            hint = " (EPS must be eps_gaap or eps_non_gaap)" if f.metric == "eps" else ""
            out.append(LabelIssue("error", i, f"unknown metric {f.metric!r}{hint}"))
        if f.unit not in GOLD_UNITS:
            out.append(LabelIssue("error", i, f"unit {f.unit!r}: use USD, pct or USD_per_share (normalised)"))
        if f.period is None:
            out.append(
                LabelIssue(
                    "error",
                    i,
                    "period is empty: an empty period matches any period; delete the "
                    "fact if the period is unclear",
                )
            )
        elif not _PERIOD_RX.match(f.period):
            out.append(LabelIssue("error", i, f"period {f.period!r}: use FY2027Q3 or FY2027"))
        if text is not None and f.quote not in text:
            out.append(LabelIssue("error", i, "quote is not found verbatim in the document"))
        if f.value is not None and not _value_printed(f.value, f.quote):
            out.append(LabelIssue("warning", i, f"value {f.value:g} not seen in the quote at any scale"))
        if f.value is not None and f.unit == "USD" and 0 < abs(f.value) < 1e5:
            out.append(
                LabelIssue("warning", i, f"USD value {f.value:g} looks unscaled (should be whole dollars)")
            )
        if f.segment and f.scope == "company":
            out.append(LabelIssue("warning", i, "segment is set but scope is company"))
        if not f.segment and f.scope == "segment":
            out.append(LabelIssue("warning", i, "scope is segment but segment is empty"))
        key = (f.metric, f.basis, f.period, (f.segment or "").strip().lower() or None)
        if key in seen:
            out.append(
                LabelIssue("error", i, f"duplicate of fact {seen[key]} (same metric/basis/period/segment)")
            )
        seen.setdefault(key, i)
    return out


def doc_kind_for(row: dict[str, Any]) -> str:
    """Label doc_kind for a manifest row: explicit for policy/news rows; SEC rows by file kind."""
    if row.get("doc_kind"):
        return str(row["doc_kind"])
    return "earnings_release" if row.get("file_kind") == "ex99" else "8k_other"
