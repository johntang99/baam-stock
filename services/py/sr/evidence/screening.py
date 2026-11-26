"""Restricted-review screen (S1 合规, S2§3.2, AC-25): suspected non-public material never reaches public views
or model features; a human reviews it."""

from __future__ import annotations

from dataclasses import dataclass

from sr.config import load


@dataclass(frozen=True)
class ScreenResult:
    visibility: str  # public | internal | restricted_review
    reasons: tuple[str, ...]


def screen(text: str, license_scope: str) -> ScreenResult:
    cfg = load("evidence")["screening"]
    low = text.lower()
    hits = tuple(m for m in cfg["mnpi_markers"] if m in low)
    if license_scope in cfg["restricted_license_scopes"]:
        hits = (*hits, f"license_scope={license_scope}")
    if hits:
        return ScreenResult("restricted_review", hits)
    return ScreenResult("internal" if license_scope == "licensed_internal" else "public", ())
