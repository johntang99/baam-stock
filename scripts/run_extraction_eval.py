"""Score an extraction provider on the reviewed gold set and record extraction_eval_runs (D-32; AC-30).

uv run python scripts/run_extraction_eval.py --provider fake [--save]       # --save writes to DATABASE/DIRECT_URL
uv run python scripts/run_extraction_eval.py --provider anthropic --allow-spend --save
"""

from __future__ import annotations

import argparse
import sys

from sr.llm.base import LLMProvider
from sr.llm.eval_extraction import run_eval, save_report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["fake", "anthropic"], default="fake")
    ap.add_argument("--allow-spend", action="store_true")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    if a.provider != "fake" and not a.allow_spend:
        print("refusing: paid API calls; pass --allow-spend after approval", file=sys.stderr)
        return 2
    if a.provider == "fake":
        from sr.llm.fake import FakeLLMProvider

        prov: LLMProvider = FakeLLMProvider()
    else:
        from sr.llm.anthropic import ClaudeProvider

        prov = ClaudeProvider()
    rep = run_eval(prov)
    print(
        f"{rep.provider}/{rep.model}/{rep.prompt_version} on {rep.label_set_version}: {rep.n_docs} reviewed docs"
    )
    for g, s in rep.scores.items():
        print(
            f"  {g:<13} P={s.precision:.3f} R={s.recall:.3f} F1={s.f1:.3f}  {'PASS' if rep.passed[g] else 'FAIL'}"
        )
    if a.save:
        from sr.db import connect

        with connect() as c:
            save_report(c, rep)
            c.commit()
        print("saved to extraction_eval_runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
