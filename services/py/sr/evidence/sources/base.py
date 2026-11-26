"""EvidenceSource interface (MP §3.2) and the raw document handed to ingest."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

ArrivalMode = Literal["live", "archived", "simulated"]


@dataclass(frozen=True)
class RawDocument:
    source_id: str
    external_ref: str  # e.g. SEC accession number, feed guid
    title: str
    content: bytes
    content_type: str  # text/html, text/plain, application/json …
    received_at: datetime  # UTC: when the system got it (archived: capture time)
    arrival_mode: ArrivalMode = "live"
    canonical_url: str | None = None
    locator: str | None = None
    source_published_at: datetime | None = None
    source_published_precision: str | None = None
    missing_reason: str | None = None  # required when source_published_at is None (DC §1, AC-06)
    available_at: datetime | None = (
        None  # archived: recorded availability; live: set by ingest (= processing done)
    )
    simulated_available_at: datetime | None = None
    subject_company_ids: tuple[str, ...] = field(default_factory=tuple)
    origin_doc_id: str | None = None  # re-publication of an original document


@dataclass(frozen=True)
class FetchFailure:
    """A listed item whose content could not be fetched (-> collection item disposition fetch_failed)."""

    source_id: str
    external_ref: str
    title: str
    url: str | None
    error: str


@runtime_checkable
class EvidenceSource(Protocol):
    source_id: str

    def poll(self, since_utc: datetime) -> list[RawDocument]: ...
