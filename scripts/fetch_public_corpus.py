"""Fetch policy and news documents for the extraction evaluation corpus (DP 1.18; D-32; OQ-41).

- policy: Federal Register documents (BIS export rules, presidential proclamations, USTR, NIST CHIPS, ITA) found
  by the queries in config/extraction_eval.yaml, newest first, round-robin across queries, size-capped.
- news: company newsroom press releases from public IR RSS feeds (D-15). Feeds list only recent items; re-run
  later to grow the set. Third-party news waits for the D-15 licence.

Raw files go to data/corpus/{fr,ir}/ (gitignored); rows are added to data/labels/extraction-v0/manifest.jsonl
(committed). Already-listed documents are skipped, so re-running only adds new ones. Requests carry a generic
client name (no contact details) and stay <= 1 request/s.

  uv run python scripts/fetch_public_corpus.py [--only policy|news]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from defusedxml import ElementTree

from sr.config import load, repo_root
from sr.evidence.hashing import normalized_text, sha256_text
from sr.evidence.sources.ir import _parse_date
from sr.evidence.sources.transport import LiveTransport, Transport

FR_FIELDS = [
    "document_number",
    "type",
    "title",
    "publication_date",
    "page_length",
    "body_html_url",
    "html_url",
]


def read_manifest_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                rows[r["doc_key"]] = r
    return rows


def write_manifest_rows(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(rows[k], ensure_ascii=False, sort_keys=True) + "\n" for k in sorted(rows))
    )


def fr_search_url(api_url: str, q: dict[str, Any], since: str) -> str:
    params: list[tuple[str, str]] = [
        ("conditions[publication_date][gte]", since),
        ("conditions[term]", str(q["term"])),
        ("order", "newest"),
        ("per_page", "100"),
    ]
    if q.get("agency"):
        params.append(("conditions[agencies][]", str(q["agency"])))
    if q.get("doc_type"):
        params.append(("conditions[type][]", str(q["doc_type"])))
    params += [("fields[]", f) for f in FR_FIELDS]
    return f"{api_url}?{urlencode(params)}"


def round_robin(
    groups: list[list[dict[str, Any]]], key: Callable[[dict[str, Any]], str]
) -> list[dict[str, Any]]:
    """Interleave the groups (each already newest first), dropping repeats of the same key."""
    out, seen = [], set()
    queues = [list(g) for g in groups]
    while any(queues):
        for q in queues:
            while q:
                rec = q.pop(0)
                if key(rec) not in seen:
                    seen.add(key(rec))
                    out.append(rec)
                    break
    return out


def _store(corpus: Path, rel: Path, raw: bytes) -> str:
    (corpus / rel).parent.mkdir(parents=True, exist_ok=True)
    (corpus / rel).write_bytes(raw)
    return normalized_text(raw, "text/html")


def fetch_policy(
    tr: Transport, plan: dict[str, Any], corpus: Path, rows: dict[str, dict[str, Any]]
) -> dict[str, int]:
    stats = {"added": 0, "skipped_type": 0, "skipped_long": 0, "skipped_failed": 0}
    have = sum(1 for r in rows.values() if r.get("file_kind") == "policy")
    groups = []
    for q in plan["queries"]:
        payload = json.loads(tr.get(fr_search_url(plan["api_url"], q, str(plan["since"]))))
        groups.append([{**rec, "_query": q["name"]} for rec in payload.get("results", [])])
    for rec in round_robin(groups, key=lambda r: str(r["document_number"])):
        if have + stats["added"] >= int(plan["max_docs"]):
            break
        key = f"fr:{rec['document_number']}"
        if key in rows:
            continue
        if rec.get("type") not in plan["types"]:
            stats["skipped_type"] += 1
            continue
        if not rec.get("body_html_url") or int(rec.get("page_length") or 0) > int(plan["max_pages"]):
            stats["skipped_long"] += 1
            continue
        try:
            raw = tr.get(str(rec["body_html_url"]))
        except OSError:
            stats["skipped_failed"] += 1
            continue
        rel = Path("fr") / f"{rec['document_number']}.html"
        text = normalized_text(raw, "text/html")
        if len(text) > int(plan["max_chars"]):
            stats["skipped_long"] += 1
            continue
        _store(corpus, rel, raw)
        rows[key] = {
            "doc_key": key,
            "doc_kind": "policy",
            "file_kind": "policy",
            "ticker": "",
            "company_id": None,
            "form": rec["type"],
            "title": rec.get("title", ""),
            "query": rec["_query"],
            "filing_date": rec["publication_date"],
            "published_precision": "day",  # FR gives dates only (OQ-29)
            "url": rec.get("html_url") or rec["body_html_url"],
            "path": rel.as_posix(),
            "content_type": "text/html",
            "sha256_raw": hashlib.sha256(raw).hexdigest(),
            "sha256_text": sha256_text(text),
            "chars": len(text),
        }
        stats["added"] += 1
    return stats


def _slug(link: str) -> str:
    parts = [p for p in urlparse(link).path.split("/") if p]
    return re.sub(r"[^A-Za-z0-9._-]+", "-", "-".join(parts[-2:]) if parts else "item")[:120]


def fetch_news(
    tr: Transport, plan: dict[str, Any], corpus: Path, rows: dict[str, dict[str, Any]]
) -> dict[str, int]:
    stats = {"added": 0, "skipped_link": 0, "skipped_short": 0, "skipped_failed": 0}
    for feed in plan["feeds"]:
        root = ElementTree.fromstring(tr.get(feed["url"]))  # untrusted XML
        items = root.findall(".//item")
        taken = 0
        for it in items:
            if taken >= int(plan["max_per_feed"]):
                break
            link = (it.findtext("link") or "").strip()
            # links are untrusted: only https press-release pages under the configured prefix are fetched
            if not link.startswith(str(feed["link_prefix"])) or urlparse(link).scheme != "https":
                stats["skipped_link"] += 1
                continue
            key = f"ir:{feed['ticker']}:{_slug(link)}"
            if key in rows:
                taken += 1
                continue
            try:
                raw = tr.get(link)
            except OSError:
                stats["skipped_failed"] += 1
                continue
            text = normalized_text(raw, "text/html")
            if len(text) < int(plan["min_chars"]):
                stats["skipped_short"] += 1
                continue
            rel = Path("ir") / str(feed["ticker"]) / f"{_slug(link)}.html"
            _store(corpus, rel, raw)
            pub = _parse_date((it.findtext("pubDate") or "").strip())
            rows[key] = {
                "doc_key": key,
                "doc_kind": "news",
                "file_kind": "news",
                "ticker": feed["ticker"],
                "company_id": f"co_{str(feed['ticker']).lower()}",
                "form": "press_release",
                "title": (it.findtext("title") or "").strip(),
                "filing_date": pub.date().isoformat() if pub else None,
                "published_at": pub.isoformat() if pub else None,
                "published_precision": "minute" if pub else "unknown",
                "url": link,
                "path": rel.as_posix(),
                "content_type": "text/html",
                "sha256_raw": hashlib.sha256(raw).hexdigest(),
                "sha256_text": sha256_text(text),
                "chars": len(text),
            }
            stats["added"] += 1
            taken += 1
    return stats


def main() -> int:
    cfg = load("extraction_eval")
    plan = cfg["corpus_plan"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["policy", "news"], default=None)
    a = ap.parse_args()
    tr: Transport = LiveTransport(None, float(plan["max_requests_per_s"]), user_agent=str(plan["user_agent"]))
    root = repo_root()
    corpus, manifest = root / cfg["paths"]["corpus"], root / cfg["paths"]["labels"] / "manifest.jsonl"
    rows = read_manifest_rows(manifest)
    if a.only in (None, "policy"):
        print("policy:", fetch_policy(tr, plan["policy"], corpus, rows), flush=True)
        write_manifest_rows(manifest, rows)
    if a.only in (None, "news"):
        print("news:", fetch_news(tr, plan["news"], corpus, rows), flush=True)
        write_manifest_rows(manifest, rows)
    kinds: dict[str, int] = {}
    for r in rows.values():
        kinds[str(r.get("file_kind"))] = kinds.get(str(r.get("file_kind")), 0) + 1
    print(f"manifest: {len(rows)} documents {kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
