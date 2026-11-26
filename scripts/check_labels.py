"""Reviewer self-check for extraction labels (DP 1.18; guide: docs/labeling/extraction-v0.md).

uv run python scripts/check_labels.py                  # check every reviewed label + progress
uv run python scripts/check_labels.py --keys <doc key>  # check specific files (drafts too)
uv run python scripts/check_labels.py --queue 10        # next documents to review, in recommended order
uv run python scripts/check_labels.py --text <doc key> > doc.txt   # the exact text quotes must come from
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from sr.config import load, repo_root
from sr.llm.eval_extraction import doc_text
from sr.llm.labels import DocLabel, labels_dir, lint_label, read_manifest, stratified


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="", help="comma-separated doc keys (default: all reviewed files)")
    ap.add_argument("--all", action="store_true", help="also check drafts")
    ap.add_argument("--queue", type=int, default=0, help="print the next N unreviewed documents and exit")
    ap.add_argument("--text", default="", help="print one document's normalised text (what quotes refer to)")
    a = ap.parse_args()
    cfg = load("extraction_eval")
    corpus = repo_root() / cfg["paths"]["corpus"]
    manifest = read_manifest()
    if a.text:
        if a.text not in manifest:
            print(f"unknown doc key: {a.text}", file=sys.stderr)
            return 2
        print(doc_text(manifest[a.text], corpus))
        return 0
    files = sorted((labels_dir() / "labels").glob("*.json"))
    labels: list[tuple[str, DocLabel | None, str]] = []
    for p in files:
        try:
            labels.append((p.name, DocLabel.model_validate_json(p.read_text()), ""))
        except Exception as e:  # malformed JSON or a field outside the schema
            labels.append((p.name, None, str(e).splitlines()[0] if str(e) else repr(e)))
    reviewed = {lab.doc_key for _, lab, _ in labels if lab and lab.label_status == "reviewed"}

    if a.queue:
        for k in stratified(manifest, [k for k in manifest if k not in reviewed])[: a.queue]:
            r = manifest[k]
            print(f"{r['ticker']:<5} {r['file_kind']:<8} {r['filing_date']}  {k}\n      {r['url']}")
        return 0

    want = {k.strip() for k in a.keys.split(",") if k.strip()}
    errors = warnings = checked = 0
    for name, lab, err in labels:
        if lab is None:
            print(f"{name}: ERROR cannot read file: {err}")
            errors += 1
            continue
        if want and lab.doc_key not in want:
            continue
        if not want and not a.all and lab.label_status != "reviewed":
            continue
        checked += 1
        row = manifest.get(lab.doc_key)
        if row is None:
            print(f"{name}: ERROR doc_key not in manifest")
            errors += 1
            continue
        try:
            text: str | None = doc_text(row, corpus)
        except FileNotFoundError:
            text = None
        for iss in lint_label(lab, text, name):
            where = "" if iss.fact is None else f" fact[{iss.fact}]"
            print(f"{name}{where}: {iss.level.upper()} {iss.message}")
            errors += iss.level == "error"
            warnings += iss.level == "warning"
    need = int(cfg["approval"]["min_reviewed_docs"])
    kinds = Counter(str(manifest[k]["file_kind"]) for k in reviewed if k in manifest)
    print(
        f"checked {checked} file(s): {errors} error(s), {warnings} warning(s). "
        f"Reviewed {len(reviewed)}/{need} needed for approval ({dict(kinds)})."
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
