"""Prediction hand-off (DC §3.5 prediction_readiness; AC-12)."""

from __future__ import annotations

from typing import Any

from sr.config import load


def allowed_models(category: str) -> list[str]:
    cfg = load("readiness")
    return (
        ["market_baseline", "event_enhanced"]
        if category in cfg["event_enhanced_validated_categories"]
        else ["market_baseline"]
    )


def stock_reaction(
    category: str, market_inputs_ready: bool, analysis_id: str | None = None
) -> dict[str, Any]:
    cfg = load("readiness")
    models = allowed_models(category)
    if not market_inputs_ready:
        out = {
            "status": "missing_inputs",
            "reason": cfg["market_inputs_pending_reason"],
            "allowed_models": models,
        }
    elif models == ["market_baseline"]:
        out = {
            "status": "ready",
            "reason": f"event_enhanced_not_validated_for_{category}",
            "allowed_models": models,
        }
    else:
        out = {"status": "ready", "reason": "event_enhanced_validated", "allowed_models": models}
    if analysis_id:
        out["analysis_id"] = analysis_id
    return out


def not_applicable(reason: str) -> dict[str, Any]:
    return {"status": "not_applicable", "reason": reason}
