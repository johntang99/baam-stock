"""Gold labels for the extraction evaluation set (DP 1.18; D-32). One JSON file per document under
<labels>/labels/<doc key>.json. Only `label_status: reviewed` files count; drafts (pre-labels) never do."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

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
