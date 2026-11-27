"""Policy/news corpus fetch for the extraction eval set (DP 1.18; D-32; OQ-41). SYNTHETIC responses, no network."""

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from sr.llm.labels import doc_kind_for, stratified
from tests.conftest import _load_script

mod = _load_script("fetch_public_corpus")
API = "https://fr.example.test/api/v1/documents.json"
BODY = "<html><body><p>Synthetic rule text (synthetic). " + "word " * 200 + "</p></body></html>"


class DictTransport:
    """url -> bytes; FR searches are keyed by their `conditions[term]` + agency/type."""

    def __init__(self, pages: dict[str, bytes]) -> None:
        self.pages, self.calls = pages, []  # type: tuple[dict[str, bytes], list[str]]

    def get(self, url: str) -> bytes:
        self.calls.append(url)
        if url.startswith(API):
            q = parse_qs(urlparse(url).query)
            url = "search:" + (q.get("conditions[agencies][]") or q.get("conditions[type][]") or ["?"])[0]
        if url not in self.pages:
            raise OSError(f"404 {url}")
        return self.pages[url]

    def meta(self, url: str) -> dict[str, Any]:
        return {}


def fr(num: str, typ: str = "Rule", pages: int = 5, day: str = "2026-01-20") -> dict[str, Any]:
    return {
        "document_number": num,
        "type": typ,
        "title": f"Synthetic {num}",
        "publication_date": day,
        "page_length": pages,
        "body_html_url": f"https://fr.example.test/full/{num}.html",
        "html_url": f"https://fr.example.test/d/{num}",
    }


def policy_plan(max_docs: int = 10) -> dict[str, Any]:
    return {
        "api_url": API,
        "since": "2023-01-01",
        "max_docs": max_docs,
        "max_pages": 15,
        "max_chars": 5000,
        "types": ["Rule", "Notice", "Presidential Document"],
        "queries": [
            {"name": "a", "agency": "agency-a", "term": "semiconductor"},
            {"name": "p", "doc_type": "PRESDOCU", "term": "semiconductor"},
        ],
    }


def search(*recs: dict[str, Any]) -> bytes:
    return json.dumps({"results": list(recs)}).encode()


def test_search_url_encodes_conditions_and_fields() -> None:
    url = mod.fr_search_url(
        API, {"agency": "industry-and-security-bureau", "term": '"advanced computing"'}, "2023-01-01"
    )
    q = parse_qs(urlparse(url).query)
    assert q["conditions[agencies][]"] == ["industry-and-security-bureau"]
    assert q["conditions[term]"] == ['"advanced computing"'] and q["order"] == ["newest"]
    assert "body_html_url" in q["fields[]"] and "page_length" in q["fields[]"]


def test_policy_round_robin_dedupe_and_caps(tmp_path: Path) -> None:
    pages = {
        "search:agency-a": search(
            fr("A1"), fr("SHARED"), fr("LONG", pages=400), fr("PR", typ="Proposed Rule"), fr("A2")
        ),
        "search:PRESDOCU": search(
            fr("SHARED", typ="Presidential Document"), fr("P1", typ="Presidential Document")
        ),
        "https://fr.example.test/full/A1.html": BODY.encode(),
        "https://fr.example.test/full/SHARED.html": BODY.encode(),
        "https://fr.example.test/full/P1.html": (
            "<p>" + "x " * 4000 + "</p>"
        ).encode(),  # too long after download
        "https://fr.example.test/full/A2.html": BODY.encode(),
    }
    rows: dict[str, dict[str, Any]] = {}
    stats = mod.fetch_policy(DictTransport(pages), policy_plan(), tmp_path, rows)
    # order: A1, SHARED (both queries; counted once), LONG (skipped), P1 (too long), PR (type), A2
    assert list(rows) == ["fr:A1", "fr:SHARED", "fr:A2"]
    assert stats == {"added": 3, "skipped_type": 1, "skipped_long": 2, "skipped_failed": 0}
    r = rows["fr:A1"]
    assert r["doc_kind"] == "policy" and r["published_precision"] == "day" and r["ticker"] == ""
    assert (tmp_path / r["path"]).exists() and doc_kind_for(r) == "policy"
    # re-running adds nothing; max_docs counts documents already listed
    tr = DictTransport(pages)
    assert mod.fetch_policy(tr, policy_plan(), tmp_path, rows)["added"] == 0
    assert mod.fetch_policy(DictTransport(pages), policy_plan(max_docs=3), tmp_path, dict(rows))["added"] == 0


RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Synthetic Corp launches X (synthetic)</title><link>https://news.example.test/news/launch-x</link>
<pubDate>Mon, 16 Nov 2026 14:00:00 -0500</pubDate></item>
<item><title>Blog post</title><link>https://blog.example.test/post</link><pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Plain http</title><link>http://news.example.test/news/insecure</link></item>
<item><title>Broken page</title><link>https://news.example.test/news/empty</link></item>
<item><title>No date</title><link>https://news.example.test/news/no-date</link></item>
</channel></rss>"""


def news_plan(max_per_feed: int = 10) -> dict[str, Any]:
    return {
        "max_per_feed": max_per_feed,
        "min_chars": 500,
        "feeds": [
            {
                "ticker": "SYN",
                "url": "https://news.example.test/rss",
                "link_prefix": "https://news.example.test/news/",
            }
        ],
    }


def test_news_filters_untrusted_links_and_short_pages(tmp_path: Path) -> None:
    pages = {
        "https://news.example.test/rss": RSS,
        "https://news.example.test/news/launch-x": BODY.encode(),
        "https://news.example.test/news/empty": b"<html><body>Loading</body></html>",
        "https://news.example.test/news/no-date": BODY.encode(),
    }
    tr = DictTransport(pages)
    rows: dict[str, dict[str, Any]] = {}
    stats = mod.fetch_news(tr, news_plan(), tmp_path, rows)
    assert stats == {"added": 2, "skipped_link": 2, "skipped_short": 1, "skipped_failed": 0}
    assert not any("blog.example.test" in c or c.startswith("http://") for c in tr.calls)  # never fetched
    r = rows["ir:SYN:news-launch-x"]
    assert r["published_at"] == "2026-11-16T19:00:00+00:00" and r["published_precision"] == "minute"
    assert r["doc_kind"] == "news" and r["company_id"] == "co_syn"
    nd = rows["ir:SYN:news-no-date"]
    assert nd["published_at"] is None and nd["published_precision"] == "unknown"
    assert mod.fetch_news(DictTransport(pages), news_plan(), tmp_path, rows)["added"] == 0


def test_feed_xml_is_parsed_safely(tmp_path: Path) -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><rss>&b;</rss>'
    with pytest.raises(Exception, match="(?i)entit"):
        mod.fetch_news(DictTransport({"https://news.example.test/rss": bomb}), news_plan(), tmp_path, {})


def test_doc_kind_and_queue_include_new_kinds() -> None:
    manifest = {
        "s1": {"ticker": "SYN", "file_kind": "ex99", "filing_date": "2026-01-01"},
        "s2": {"ticker": "SYN", "file_kind": "primary", "filing_date": "2026-01-01"},
        "p1": {"ticker": "", "file_kind": "policy", "doc_kind": "policy", "filing_date": "2026-01-02"},
        "n1": {"ticker": "SYN", "file_kind": "news", "doc_kind": "news", "filing_date": "2026-01-03"},
    }
    assert [doc_kind_for(manifest[k]) for k in ("s1", "s2", "p1", "n1")] == [
        "earnings_release",
        "8k_other",
        "policy",
        "news",
    ]
    assert set(stratified(manifest, list(manifest))[:4]) == {"s1", "s2", "p1", "n1"}
