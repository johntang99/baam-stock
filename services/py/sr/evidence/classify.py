"""Rules-based channel / category / relevance classification for collection items (DP 1.27; D-45)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from sr.config import load


@dataclass(frozen=True)
class Classification:
    channel: str
    category: str
    category_confidence: float
    relevance: float
    mentions: tuple[str, ...]
    reason: str


@cache
def _company_terms() -> dict[str, tuple[str, ...]]:
    """company_id -> lower-case terms (ticker + configured aliases)."""
    uni = load("universe")["securities"]
    aliases = load("collection")["aliases"]
    out: dict[str, tuple[str, ...]] = {}
    for s in uni:
        cid = "co_" + str(s.get("id") or s["ticker"]).lower().lstrip("^")
        out[cid] = (s["ticker"].lower(), *[a.lower() for a in aliases.get(cid, [])])
    return out


def mentions(text: str) -> tuple[str, ...]:
    low = text.lower()
    found = []
    for cid, terms in _company_terms().items():
        for term in terms:
            if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", low):
                found.append(cid)
                break
    return tuple(sorted(found))


def categorize(text: str) -> tuple[str, float]:
    low = text.lower()
    scores = {cat: sum(low.count(k) for k in kws) for cat, kws in load("collection")["categories"].items()}
    total = sum(scores.values())
    if total == 0:
        return "other", 0.0
    best = max(scores, key=lambda c: (scores[c], c == "earnings_guidance"))
    return best, round(scores[best] / total, 4)


def channel_for(
    source_kind: str, subject_company_ids: list[str], target_company_id: str, peer_company_ids: set[str]
) -> str:
    ch: str = load("collection")["channel_by_source_kind"][source_kind]
    if (
        ch in ("filing", "company_ir")
        and subject_company_ids
        and target_company_id not in subject_company_ids
        and peer_company_ids & set(subject_company_ids)
    ):
        return "peer_company"
    return ch


def relevance(
    text: str,
    subject_company_ids: list[str],
    target_company_id: str,
    peer_company_ids: set[str],
    topic_linked: bool,
) -> tuple[float, str, tuple[str, ...]]:
    r = load("collection")["relevance"]
    m = mentions(text)
    if target_company_id in subject_company_ids:
        return float(r["subject"]), "subject_company", m
    if target_company_id in m:
        return float(r["named"]), "named_in_text", m
    if topic_linked:
        return float(r["linked_topic"]), "policy_topic_link", m
    if peer_company_ids & (set(subject_company_ids) | set(m)):
        return float(r["peer"]), "peer_company", m
    return float(r["none"]), "no_mention", m


def classify(
    text: str,
    source_kind: str,
    subject_company_ids: list[str],
    target_company_id: str,
    peer_company_ids: set[str],
    topic_linked: bool = False,
) -> Classification:
    cat, conf = categorize(text)
    rel, why, m = relevance(text, subject_company_ids, target_company_id, peer_company_ids, topic_linked)
    return Classification(
        channel_for(source_kind, subject_company_ids, target_company_id, peer_company_ids),
        cat,
        conf,
        rel,
        m,
        why,
    )
