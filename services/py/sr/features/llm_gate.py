"""D-32 gate (AC-30): LLM-extracted facts may feed model features only when the exact provider / model /
prompt_version passed the extraction evaluation on enough reviewed documents. Otherwise feature building refuses."""

from __future__ import annotations

from typing import Any

from sr.config import load
from sr.db import Conn


class PromptNotApproved(RuntimeError):
    pass


def require_approved(conn: Conn, provider: str, model: str, prompt_version: str) -> None:
    cfg = load("extraction_eval")
    gated = [g for g, gate in cfg["gates"].items() if gate]
    rows = conn.execute(
        """select distinct on (field_group) field_group, passed, n_docs from extraction_eval_runs
           where llm_provider = %s and llm_model = %s and prompt_version = %s and label_set_version = %s
           order by field_group, created_at desc""",
        (provider, model, prompt_version, cfg["label_set_version"]),
    ).fetchall()
    latest = {r["field_group"]: r for r in rows}
    problems = []
    for g in gated:
        r = latest.get(g)
        if r is None:
            problems.append(f"{g}: no evaluation run")
        elif not r["passed"]:
            problems.append(f"{g}: below D-32 threshold")
        elif r["n_docs"] < int(cfg["approval"]["min_reviewed_docs"]):
            problems.append(f"{g}: only {r['n_docs']} reviewed documents")
    if problems:
        raise PromptNotApproved(
            f"{provider}/{model}/{prompt_version} not approved for features: " + "; ".join(problems)
        )


def event_feature_inputs(
    conn: Conn, analysis_id: str, fields: tuple[str, ...] = ("facts",)
) -> dict[str, Any]:
    """Facts of an analysis version as feature inputs — only from approved extraction prompts (AC-30). Asking for an
    explanation-only field (e.g. market_explanation.valuation_context) raises ExplanationOnlyField (AC-42)."""
    from sr.events.valuation import check_feature_inputs

    check_feature_inputs(fields)
    if set(fields) - {"facts"}:
        raise ValueError(f"only analysis facts can be feature inputs, not {sorted(set(fields) - {'facts'})}")
    row = conn.execute(
        "select facts, model_versions from event_analysis_versions where analysis_id = %s", (analysis_id,)
    ).fetchone()
    if row is None:
        raise KeyError(analysis_id)
    mv = row["model_versions"] or {}
    if mv.get("llm_provider"):
        require_approved(conn, mv["llm_provider"], mv["llm_model"], mv.get("llm_prompt_version", "unknown"))
    return {"analysis_id": analysis_id, "facts": row["facts"] or []}
