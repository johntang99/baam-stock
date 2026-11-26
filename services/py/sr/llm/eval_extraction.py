"""Extraction evaluation (DP 1.18; D-32; AC-30). Runs a provider over the reviewed gold documents (replay mode,
no tools), applies the same deterministic fact checks as production, and scores four field groups:

- numeric_fact: predicted facts vs gold — a match needs the same canonical metric and period and an equal value
  (normalised units, relative tolerance). Precision = matches / predicted, recall = matches / gold.
- direction / scope / certainty: macro precision / recall / F1 of the label on matched facts.

Results go to extraction_eval_runs (one row per field group) with `passed` from the configured gates.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sr.config import load, repo_root
from sr.db import Conn
from sr.events.factcheck import CheckedFact, check_facts
from sr.evidence.hashing import normalized_text, sha256_text
from sr.ids import new_id
from sr.llm.base import LLMProvider
from sr.llm.labels import DocLabel, GoldFact, read_labels, read_manifest

GROUPS = ("numeric_fact", "direction", "scope", "certainty")


@dataclass
class GroupScore:
    precision: float
    recall: float
    f1: float


@dataclass
class EvalReport:
    label_set_version: str
    provider: str
    model: str
    prompt_version: str
    n_docs: int
    scores: dict[str, GroupScore]
    passed: dict[str, bool]
    details: list[dict[str, Any]] = field(default_factory=list)


def _f1(p: float, r: float) -> float:
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def _value_eq(a: float | None, b: float | None, rel: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= rel * max(1.0, abs(b))


def match(pred: list[CheckedFact], gold: list[GoldFact], rel: float) -> list[tuple[CheckedFact, GoldFact]]:
    """Greedy one-to-one matching on (metric, period, value)."""
    free = list(gold)
    pairs = []
    for p in pred:
        for g in free:
            if (
                p.metric == g.metric
                and (g.period is None or p.period == g.period)
                and _value_eq(p.value, g.value, rel)
            ):
                pairs.append((p, g))
                free.remove(g)
                break
    return pairs


def label_scores(pairs: list[tuple[str | None, str]]) -> GroupScore:
    """Macro P/R/F1 over the gold label classes present (pred None counts as a miss)."""
    classes = sorted({g for _, g in pairs})
    if not classes:
        return GroupScore(0.0, 0.0, 0.0)
    ps, rs = [], []
    for c in classes:
        tp = sum(1 for p, g in pairs if p == c and g == c)
        pred_c = sum(1 for p, _ in pairs if p == c)
        gold_c = sum(1 for _, g in pairs if g == c)
        ps.append(tp / pred_c if pred_c else 0.0)
        rs.append(tp / gold_c if gold_c else 0.0)
    p, r = sum(ps) / len(ps), sum(rs) / len(rs)
    return GroupScore(p, r, _f1(p, r))


def doc_text(manifest_row: dict[str, Any], corpus_root: Path) -> str:
    raw = (corpus_root / str(manifest_row["path"])).read_bytes()
    return normalized_text(raw, str(manifest_row.get("content_type", "text/html")))


def run_eval(
    provider: LLMProvider,
    labels: list[DocLabel] | None = None,
    labels_root: Path | None = None,
    corpus_root: Path | None = None,
) -> EvalReport:
    cfg = load("extraction_eval")
    rel = float(cfg["matching"]["value_rel_tolerance"])
    labels = (
        read_labels(labels_root) if labels is None else [x for x in labels if x.label_status == "reviewed"]
    )
    manifest = read_manifest(labels_root)
    corpus_root = corpus_root or repo_root() / cfg["paths"]["corpus"]
    n_pred = n_gold = n_tp = 0
    lab_pairs: dict[str, list[tuple[str | None, str]]] = defaultdict(list)
    details = []
    for lab in labels:
        row = manifest.get(lab.doc_key)
        if row is None:
            raise KeyError(f"{lab.doc_key}: not in manifest")
        text = doc_text(row, corpus_root)
        if sha256_text(text) != lab.text_sha256:
            raise ValueError(f"{lab.doc_key}: document text changed since labelling (sha mismatch)")
        ext = provider.extract_facts(text, mode="replay")
        pred = check_facts(ext.facts, lab.fiscal_period).accepted if ext.status == "succeeded" else []
        pairs = match(pred, lab.facts, rel)
        n_pred, n_gold, n_tp = n_pred + len(pred), n_gold + len(lab.facts), n_tp + len(pairs)
        for pf, gf in pairs:
            lab_pairs["direction"].append((pf.direction, gf.direction))
            lab_pairs["scope"].append((pf.scope, gf.scope))
            lab_pairs["certainty"].append((pf.certainty, gf.certainty))
        details.append(
            {
                "doc_key": lab.doc_key,
                "status": ext.status,
                "predicted": len(pred),
                "gold": len(lab.facts),
                "matched": len(pairs),
            }
        )
    precision = n_tp / n_pred if n_pred else 0.0
    recall = n_tp / n_gold if n_gold else 0.0
    scores = {"numeric_fact": GroupScore(precision, recall, _f1(precision, recall))}
    for g in ("direction", "scope", "certainty"):
        scores[g] = label_scores(lab_pairs[g])
    passed = {}
    for g in GROUPS:
        gate = cfg["gates"].get(g)
        passed[g] = True if not gate else getattr(scores[g], gate["metric"]) >= float(gate["min"])
    return EvalReport(
        cfg["label_set_version"],
        provider.provider,
        provider.model,
        getattr(provider, "version", "unknown"),
        len(labels),
        scores,
        passed,
        details,
    )


def save_report(conn: Conn, rep: EvalReport, now: datetime | None = None) -> list[str]:
    ids = []
    for g in GROUPS:
        s = rep.scores[g]
        rid = new_id("xev")
        conn.execute(
            """insert into extraction_eval_runs (eval_run_id, label_set_version, llm_provider, llm_model, prompt_version,
                 field_group, precision, recall, f1, n_docs, passed, created_at)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                rid,
                rep.label_set_version,
                rep.provider,
                rep.model,
                rep.prompt_version,
                g,
                round(s.precision, 6),
                round(s.recall, 6),
                round(s.f1, 6),
                rep.n_docs,
                rep.passed[g],
                now or datetime.now(UTC),
            ),
        )
        ids.append(rid)
    return ids
