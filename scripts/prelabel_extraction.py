"""Draft labels for human review (DP 1.18). Writes label_status=draft files; drafts never count in evaluation —
a reviewer must correct each one and set label_status=reviewed + labeled_by=<name>.

  uv run python scripts/prelabel_extraction.py --provider fake               # free, offline
  uv run python scripts/prelabel_extraction.py --provider anthropic --allow-spend --limit 20   # paid API calls
"""

from __future__ import annotations

import argparse
import sys

from sr.config import load, repo_root
from sr.events.factcheck import check_facts
from sr.evidence.hashing import sha256_text
from sr.llm.base import LLMProvider
from sr.llm.eval_extraction import doc_text
from sr.llm.labels import DocLabel, GoldFact, read_labels, read_manifest, write_label


def provider_for(name: str) -> LLMProvider:
    if name == "fake":
        from sr.llm.fake import FakeLLMProvider

        return FakeLLMProvider()
    from sr.llm.anthropic import ClaudeProvider

    return ClaudeProvider()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["fake", "anthropic"], default="fake")
    ap.add_argument("--allow-spend", action="store_true", help="required for paid providers")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.provider != "fake" and not a.allow_spend:
        print(
            "refusing: the anthropic provider makes paid API calls; pass --allow-spend after approval",
            file=sys.stderr,
        )
        return 2
    cfg = load("extraction_eval")
    corpus = repo_root() / cfg["paths"]["corpus"]
    done = {x.doc_key for x in read_labels(reviewed_only=False)}
    prov = provider_for(a.provider)
    n = 0
    for key, row in read_manifest().items():
        if key in done:
            continue
        text = doc_text(row, corpus)
        ext = prov.extract_facts(text, mode="replay")
        facts = check_facts(ext.facts, None).accepted if ext.status == "succeeded" else []
        write_label(
            DocLabel(
                doc_key=key,
                text_sha256=sha256_text(text),
                doc_kind="earnings_release" if row["file_kind"] == "ex99" else "8k_other",
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
                        }
                    )
                    for f in facts
                ],
            )
        )
        n += 1
        if a.limit and n >= a.limit:
            break
    print(f"wrote {n} draft labels (status=draft; review required before they count)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
