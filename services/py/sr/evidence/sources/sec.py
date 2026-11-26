"""SEC EDGAR filings source (D-15): submissions JSON -> primary documents of configured forms.

Phase 1 reads archives (ArchiveTransport); live polling needs SEC_EDGAR_USER_AGENT.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sr.config import load
from sr.evidence.sources.base import ArrivalMode, RawDocument
from sr.evidence.sources.transport import Transport
from sr.timeguard import ensure_utc


def parse_acceptance(value: str, tz_name: str) -> datetime:
    """EDGAR acceptanceDateTime, e.g. '2026-11-19T16:20:31.000Z'. The wall clock is interpreted in tz_name
    (config: America/New_York, see OQ-25) and converted to UTC."""
    naive = datetime.fromisoformat(value.rstrip("Z").split("+")[0])
    return naive.replace(tzinfo=ZoneInfo(tz_name)).astimezone(UTC)


class SecEdgarSource:
    def __init__(
        self,
        ciks: dict[str, str],  # 10-digit CIK -> company_id
        transport: Transport,
        arrival_mode: ArrivalMode = "archived",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        forms: list[str] | None = None,
    ) -> None:
        self.cfg: dict[str, Any] = load("evidence")["sec_edgar"]
        self.source_id: str = self.cfg["source_id"]
        self.ciks = ciks
        self.transport = transport
        self.arrival_mode = arrival_mode
        self.clock = clock
        self.forms = set(forms or self.cfg["forms"])

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        since = ensure_utc(since_utc, "since_utc")
        out: list[RawDocument] = []
        for cik, company_id in sorted(self.ciks.items()):
            sub = json.loads(self.transport.get(self.cfg["submissions_url"].format(cik=cik)))
            recent = sub.get("filings", {}).get("recent", {})
            n = len(recent.get("accessionNumber", []))
            for i in range(n):
                form = recent["form"][i]
                if form not in self.forms:
                    continue
                accepted = parse_acceptance(
                    recent["acceptanceDateTime"][i], self.cfg["acceptance_datetime_tz"]
                )
                if accepted <= since:
                    continue
                accession = recent["accessionNumber"][i]
                url = self.cfg["archive_url"].format(
                    cik_int=int(cik),
                    accession_nodash=accession.replace("-", ""),
                    primary_document=recent["primaryDocument"][i],
                )
                out.append(
                    self._document(url, accession, form, sub.get("name", company_id), company_id, accepted)
                )
        return sorted(out, key=lambda d: (d.source_published_at or d.received_at, d.external_ref))

    def _document(
        self, url: str, accession: str, form: str, name: str, company_id: str, accepted: datetime
    ) -> RawDocument:
        content = self.transport.get(url)
        now = ensure_utc(self.clock(), "clock").to_pydatetime()
        received, available, simulated = now, None, None
        if self.arrival_mode == "archived":
            meta = self.transport.meta(url)
            if "received_at" not in meta:
                raise ValueError(f"archived document without capture metadata (received_at): {url}")
            received = ensure_utc(datetime.fromisoformat(meta["received_at"]), "received_at").to_pydatetime()
            available = ensure_utc(
                datetime.fromisoformat(meta.get("available_at", meta["received_at"])), "available_at"
            ).to_pydatetime()
        elif self.arrival_mode == "simulated":
            simulated = accepted + timedelta(seconds=int(load("evidence")["simulated_arrival"]["delay_s"]))
        return RawDocument(
            source_id=self.source_id,
            external_ref=accession,
            title=f"{form} {name}",
            content=content,
            content_type="text/html",
            received_at=received,
            arrival_mode=self.arrival_mode,
            canonical_url=url,
            locator=f"sec:{accession}",
            source_published_at=accepted,
            source_published_precision=self.cfg["published_precision"],
            available_at=available,
            simulated_available_at=simulated,
            subject_company_ids=(company_id,),
        )
