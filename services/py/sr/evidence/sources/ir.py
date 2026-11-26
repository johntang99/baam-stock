"""Company investor-relations RSS/Atom feeds (D-15). Feeds are untrusted XML -> parsed with defusedxml."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from sr.config import load
from sr.evidence.sources.base import ArrivalMode, RawDocument
from sr.evidence.sources.transport import Transport
from sr.timeguard import ensure_utc

ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass(frozen=True)
class Feed:
    company_id: str
    url: str
    precision: str | None = None


def _text(el: Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        d = parsedate_to_datetime(value)  # RSS 2.0 (RFC 822)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))  # Atom (RFC 3339)
        except ValueError:
            return None
    if d.tzinfo is None:
        return None  # no zone => cannot place in time; treat as missing
    return d.astimezone(UTC)


class IrFeedSource:
    def __init__(
        self,
        feeds: list[Feed],
        transport: Transport,
        arrival_mode: ArrivalMode = "archived",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.cfg: dict[str, Any] = load("evidence")["company_ir"]
        self.source_id: str = self.cfg["source_id"]
        self.feeds, self.transport, self.arrival_mode, self.clock = feeds, transport, arrival_mode, clock

    def _items(self, root: Element) -> list[dict[str, str]]:
        out = []
        for it in root.iter("item"):
            out.append(
                {
                    "guid": _text(it.find("guid")) or _text(it.find("link")),
                    "link": _text(it.find("link")),
                    "title": _text(it.find("title")),
                    "body": _text(it.find("description")),
                    "date": _text(it.find("pubDate")),
                }
            )
        for it in root.iter(f"{ATOM}entry"):
            link = it.find(f"{ATOM}link")
            href = link.get("href", "") if link is not None else ""
            out.append(
                {
                    "guid": _text(it.find(f"{ATOM}id")) or href,
                    "link": href,
                    "title": _text(it.find(f"{ATOM}title")),
                    "body": _text(it.find(f"{ATOM}summary")) or _text(it.find(f"{ATOM}content")),
                    "date": _text(it.find(f"{ATOM}published")) or _text(it.find(f"{ATOM}updated")),
                }
            )
        return out

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        since = ensure_utc(since_utc, "since_utc")
        docs: list[RawDocument] = []
        for feed in self.feeds:
            root = ElementTree.fromstring(self.transport.get(feed.url))
            meta = self.transport.meta(feed.url)
            for item in self._items(root):
                if not item["guid"]:
                    continue
                published = _parse_date(item["date"])
                if published is not None and published <= since:
                    continue
                now = ensure_utc(self.clock(), "clock").to_pydatetime()
                received, available = now, None
                if self.arrival_mode == "archived":
                    if "received_at" not in meta:
                        raise ValueError(f"archived feed without capture metadata (received_at): {feed.url}")
                    received = ensure_utc(
                        datetime.fromisoformat(meta["received_at"]), "received_at"
                    ).to_pydatetime()
                    available = received
                docs.append(
                    RawDocument(
                        source_id=self.source_id,
                        external_ref=item["guid"],
                        title=item["title"],
                        content=f"{item['title']}\n\n{item['body']}".encode(),
                        content_type="text/plain",
                        received_at=received,
                        arrival_mode=self.arrival_mode,
                        canonical_url=item["link"] or None,
                        locator=f"ir:{feed.company_id}:{item['guid']}",
                        source_published_at=published,
                        source_published_precision=(feed.precision or self.cfg["default_precision"])
                        if published
                        else None,
                        missing_reason=None if published else self.cfg["missing_pubdate_reason"],
                        available_at=available,
                        subject_company_ids=(feed.company_id,),
                    )
                )
        return docs
