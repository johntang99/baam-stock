"""Draft labels for human review (DP 1.18). Writes label_status=draft files; drafts never count in evaluation —
a reviewer must correct each one and set label_status=reviewed + labeled_by=<name>. Reviewed labels are never
overwritten.

  uv run python scripts/prelabel_extraction.py --provider fake                       # free, offline
  uv run python scripts/prelabel_extraction.py --provider anthropic --allow-spend \\
      --replace-drafts --sample stratified --limit 20 [--log-db]                    # paid API calls
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from sr.config import load, repo_root
from sr.events.factcheck import check_facts
from sr.evidence.hashing import sha256_text
from sr.llm.base import CallLogger, CallRecord, ListCallLogger, LLMProvider, PgCallLogger
from sr.llm.eval_extraction import doc_text
from sr.llm.labels import (
    DocLabel,
    GoldFact,
    doc_kind_for,
    labels_dir,
    read_labels,
    read_manifest,
    safe_key,
    stratified,
    write_label,
)


class TeeLogger:
    def __init__(self, *loggers: CallLogger) -> None:
        self.loggers = loggers

    def log(self, rec: CallRecord) -> None:
        for lg in self.loggers:
            lg.log(rec)


def provider_for(name: str, logger: CallLogger) -> LLMProvider:
    if name == "fake":
        from sr.llm.fake import FakeLLMProvider

        return FakeLLMProvider(logger=logger)
    from sr.llm.anthropic import ClaudeProvider

    return ClaudeProvider(logger=logger)


def to_gold(f: Any) -> GoldFact:
    return GoldFact.model_validate(
        {
            "metric": f.metric,
            "value": f.value,
            "unit": f.unit,
            "period": f.period,
            "basis": f.basis if f.basis in ("gaap", "non_gaap", "company_defined") else None,
            "quote": f.quote,
            "direction": f.direction or "none",
            "scope": f.scope or "company",
            "certainty": f.certainty or "reported",
            "segment": f.segment,
        }
    )


def recheck(manifest: dict[str, dict[str, Any]], existing: dict[str, DocLabel], corpus: Any) -> int:
    """Re-apply the deterministic checker to saved candidates; only drafts are rewritten."""
    from sr.llm.base import ExtractedFact

    n = 0
    for path in sorted((labels_dir() / "candidates").glob("*.json")):
        d = json.loads(path.read_text())
        key = d["doc_key"]
        if key not in manifest or (key in existing and existing[key].label_status == "reviewed"):
            continue
        if d["extraction_status"] != "succeeded":
            continue
        facts = tuple(ExtractedFact(**c) for c in d["candidates"])
        text = doc_text(manifest[key], corpus)
        rep = check_facts(facts, None, text)
        prev = existing.get(key)
        text_sha = sha256_text(text)
        if prev and prev.text_sha256 != text_sha:
            print(f"skip {key}: document text changed since drafting", file=sys.stderr)
            continue
        write_label(
            DocLabel(
                doc_key=key,
                text_sha256=text_sha,
                doc_kind=doc_kind_for(manifest[key]),
                label_status="draft",
                labeled_by=prev.labeled_by if prev else "prelabel:recheck",
                facts=[to_gold(f) for f in rep.accepted],
            )
        )
        d["dropped"] = rep.rejected
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        n += 1
    print(f"rechecked {n} drafts from saved candidates (no API calls)")
    return 0


def cost(records: list[CallRecord]) -> tuple[int, int, float]:
    prices = load("llm").get("pricing_usd_per_mtok", {})
    tin = sum(int(r.usage.get("input_tokens", 0)) for r in records)
    tout = sum(int(r.usage.get("output_tokens", 0)) for r in records)
    usd = 0.0
    for r in records:
        p = prices.get(r.model)
        if p:
            usd += (
                r.usage.get("input_tokens", 0) / 1e6 * p["input"]
                + r.usage.get("output_tokens", 0) / 1e6 * p["output"]
            )
    return tin, tout, usd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["fake", "anthropic"], default="fake")
    ap.add_argument("--allow-spend", action="store_true", help="required for paid providers")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--replace-drafts", action="store_true", help="re-draft documents whose label is still a draft"
    )
    ap.add_argument("--sample", choices=["first", "stratified"], default="first")
    ap.add_argument("--keys", default="", help="comma-separated doc keys to process (overrides --sample)")
    ap.add_argument("--exclude", default="", help="comma-separated doc keys to skip")
    ap.add_argument("--log-db", action="store_true", help="also write every call to llm_calls (DIRECT_URL)")
    ap.add_argument(
        "--recheck",
        action="store_true",
        help="rebuild drafts from saved candidates with the current checker (no API calls)",
    )
    a = ap.parse_args()
    if a.provider != "fake" and not a.allow_spend:
        print(
            "refusing: the anthropic provider makes paid API calls; pass --allow-spend after approval",
            file=sys.stderr,
        )
        return 2
    cfg = load("extraction_eval")
    corpus = repo_root() / cfg["paths"]["corpus"]
    manifest = read_manifest()
    existing = {x.doc_key: x for x in read_labels(reviewed_only=False)}
    skip = {k for k, lab in existing.items() if lab.label_status == "reviewed" or not a.replace_drafts}
    skip |= {k.strip() for k in a.exclude.split(",") if k.strip()}
    if a.keys:
        todo = [k.strip() for k in a.keys.split(",") if k.strip()]
        missing = [k for k in todo if k not in manifest]
        if missing:
            print(f"unknown doc keys: {missing}", file=sys.stderr)
            return 2
        todo = [k for k in todo if k not in skip]
    else:
        todo = [k for k in manifest if k not in skip]
        if a.sample == "stratified":
            todo = stratified(manifest, todo)
    if a.limit:
        todo = todo[: a.limit]

    if a.recheck:
        return recheck(manifest, existing, corpus)
    memory = ListCallLogger()
    conn = None
    if a.log_db:
        from sr.db import connect

        conn = connect(autocommit=True)
    logger: CallLogger = TeeLogger(memory, PgCallLogger(conn)) if conn else memory
    prov = provider_for(a.provider, logger)
    for i, key in enumerate(todo, 1):
        row = manifest[key]
        text = doc_text(row, corpus)
        ext = prov.extract_facts(text, mode="replay")
        rep = check_facts(ext.facts, None, text) if ext.status == "succeeded" else None
        facts = rep.accepted if rep else []
        # every candidate + why the checker dropped it, so reviewers see what the model found (not counted in eval)
        cand_dir = labels_dir() / "candidates"
        cand_dir.mkdir(parents=True, exist_ok=True)
        (cand_dir / f"{safe_key(key)}.json").write_text(
            json.dumps(
                {
                    "doc_key": key,
                    "extraction_status": ext.status,
                    "llm_call_id": ext.call_id,
                    "candidates": [asdict(f) for f in ext.facts],
                    "dropped": rep.rejected if rep else [],
                    "validation_notes": list(ext.rejected),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        write_label(
            DocLabel(
                doc_key=key,
                text_sha256=sha256_text(text),
                doc_kind=doc_kind_for(row),
                label_status="draft",
                labeled_by=f"prelabel:{prov.provider}/{prov.model}/{getattr(prov, 'version', '?')}",
                facts=[
                    GoldFact.model_validate(
                        {
                            "metric": f.metric,
                            "value": f.value,
                            "unit": f.unit,
                            "period": f.period,
                            "basis": f.basis if f.basis in ("gaap", "non_gaap", "company_defined") else None,
                            "quote": f.quote,
                            "direction": f.direction or "none",
                            "scope": f.scope or "company",
                            "certainty": f.certainty or "reported",
                            "segment": f.segment,
                        }
                    )
                    for f in facts
                ],
            )
        )
        rec = memory.records[-1]
        rejected = len(rep.rejected) if rep else 0
        print(
            f"[{i}/{len(todo)}] {row['ticker']:<4} {row['file_kind']:<7} {key:<48} {ext.status:<19} "
            f"facts={len(facts):<3} dropped_by_check={rejected:<2} in={rec.usage.get('input_tokens', 0):>6} "
            f"out={rec.usage.get('output_tokens', 0):>5} {rec.latency_ms or 0:>6}ms model={rec.model}"
            + (f" note={ext.rejected[0][:70]!r}" if ext.rejected else ""),
            flush=True,
        )
    tin, tout, usd = cost(memory.records)
    print(
        f"wrote {len(todo)} draft labels; tokens in={tin:,} out={tout:,}; est. cost ${usd:.2f} (list price)"
    )
    if conn:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
