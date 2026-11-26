"""Federal Register documents API (D-15, free). One RawDocument per document; content = the API record (JSON).

publication_date is a date => source_published_precision=day (must not order intraday events, DC §1; OQ-29).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from sr.config import load
from sr.evidence.sources.base import ArrivalMode, RawDocument
from sr.evidence.sources.transport import Transport
from sr.timeguard import ensure_utc

ET = ZoneInfo("America/New_York")


def date_et_midnight(d: str) -> datetime:
    return datetime.combine(date.fromisoformat(d), time(0, 0), tzinfo=ET).astimezone(UTC)


class FederalRegisterSource:
    def __init__(
        self,
        transport: Transport,
        arrival_mode: ArrivalMode = "archived",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.cfg: dict[str, Any] = load("policy_templates")["federal_register"]
        self.source_id: str = self.cfg["source_id"]
        self.transport, self.arrival_mode, self.clock = transport, arrival_mode, clock

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        since = ensure_utc(since_utc, "since_utc").tz_convert(ET).date().isoformat()
        out: list[RawDocument] = []
        for agency in self.cfg["agencies"]:
            url = self.cfg["search_url"].format(agency=agency, since=since)
            payload = json.loads(self.transport.get(url))
            meta = self.transport.meta(url)
            for rec in payload.get("results", []):
                now = ensure_utc(self.clock(), "clock").to_pydatetime()
                received, available = now, None
                if self.arrival_mode == "archived":
                    if "received_at" not in meta:
                        raise ValueError(f"archived search result without capture metadata: {url}")
                    received = ensure_utc(
                        datetime.fromisoformat(meta["received_at"]), "received_at"
                    ).to_pydatetime()
                    available = received
                out.append(
                    RawDocument(
                        source_id=self.source_id,
                        external_ref=rec["document_number"],
                        title=rec.get("title", ""),
                        content=json.dumps(rec, sort_keys=True, ensure_ascii=False).encode(),
                        content_type="application/json",
                        received_at=received,
                        arrival_mode=self.arrival_mode,
                        canonical_url=rec.get("html_url"),
                        locator=f"fr:{rec['document_number']}",
                        source_published_at=date_et_midnight(rec["publication_date"]),
                        source_published_precision=self.cfg["published_precision"],
                        available_at=available,
                    )
                )
        return out
