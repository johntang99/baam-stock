"""DP 1.03: SEC EDGAR + IR feed adapters reading SYNTHETIC archives (no network)."""

from datetime import UTC, datetime, timedelta

import pytest
from defusedxml import EntitiesForbidden

from sr.evidence.hashing import content_hash
from sr.evidence.screening import screen
from sr.evidence.sources.base import EvidenceSource
from sr.evidence.sources.ir import Feed, IrFeedSource
from sr.evidence.sources.sec import SecEdgarSource, parse_acceptance
from sr.evidence.sources.transport import ArchiveTransport, LiveTransport
from tests.conftest import EVIDENCE_ARCHIVE

CIKS = {"0009999001": "co_nvda"}
SINCE = datetime(2026, 11, 1, tzinfo=UTC)


def sec(mode: str = "archived") -> SecEdgarSource:
    return SecEdgarSource(
        CIKS,
        ArchiveTransport(EVIDENCE_ARCHIVE),
        arrival_mode=mode,  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 11, 26, 12, 0, tzinfo=UTC),
    )


def test_acceptance_time_is_eastern_wall_clock() -> None:
    # 16:20:31 ET on 2026-11-19 (EST, UTC-5) -> 21:20:31Z (OQ-25: verify on a real sample)
    assert parse_acceptance("2026-11-19T16:20:31.000Z", "America/New_York") == datetime(
        2026, 11, 19, 21, 20, 31, tzinfo=UTC
    )
    assert parse_acceptance("2026-07-01T16:00:00.000Z", "America/New_York").hour == 20  # EDT, UTC-4


def test_sec_poll_filters_forms_and_since() -> None:
    src = sec()
    assert isinstance(src, EvidenceSource)
    docs = src.poll(SINCE)
    assert [d.external_ref for d in docs] == [
        "0009999001-26-000101",
        "0009999001-26-000102",
    ]  # form 4 + old excluded
    d = docs[0]
    assert d.source_id == "src_sec_edgar" and d.subject_company_ids == ("co_nvda",)
    assert (
        d.source_published_at == datetime(2026, 11, 19, 21, 20, 31, tzinfo=UTC)
        and d.source_published_precision == "s"
    )
    assert d.received_at == datetime(2026, 11, 19, 21, 20, 45, tzinfo=UTC)  # from archive capture metadata
    assert d.available_at == datetime(2026, 11, 19, 21, 21, 5, tzinfo=UTC)
    assert d.arrival_mode == "archived" and b"Revenue for the quarter was $35.1 billion" in d.content
    assert sec().poll(datetime(2026, 11, 19, 21, 22, tzinfo=UTC))[0].external_ref == "0009999001-26-000102"


def test_sec_simulated_arrival() -> None:
    d = sec("simulated").poll(SINCE)[0]
    assert d.arrival_mode == "simulated" and d.available_at is None
    assert d.simulated_available_at == d.source_published_at + timedelta(seconds=60)  # type: ignore[operator]


def test_archived_document_without_capture_metadata_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import shutil

    shutil.copytree(EVIDENCE_ARCHIVE, tmp_path / "a")
    next((tmp_path / "a").rglob("form8k.htm.meta.json")).unlink()
    with pytest.raises(ValueError, match="capture metadata"):
        SecEdgarSource(CIKS, ArchiveTransport(tmp_path / "a")).poll(SINCE)


def test_archive_transport_refuses_path_escape() -> None:
    with pytest.raises(ValueError):
        ArchiveTransport(EVIDENCE_ARCHIVE).get("https://data.sec.gov/../../../etc/passwd")


def test_live_transport_requires_identifying_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError):
        LiveTransport("SEC_EDGAR_USER_AGENT", 10)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "baam-stock research contact@example.com")
    with pytest.raises(RuntimeError):
        LiveTransport("SEC_EDGAR_USER_AGENT", 10)  # placeholder from .env.example is refused


def test_ir_feed() -> None:
    src = IrFeedSource(
        [Feed("co_nvda", "https://ir.synthetic.test/feed.xml")], ArchiveTransport(EVIDENCE_ARCHIVE)
    )
    docs = {d.external_ref: d for d in src.poll(SINCE)}
    assert set(docs) == {"ir-2026-11-19-results", "ir-undated-note", "ir-leak"}
    r = docs["ir-2026-11-19-results"]
    assert (
        r.source_published_at == datetime(2026, 11, 19, 21, 20, tzinfo=UTC)
        and r.source_published_precision == "minute"
    )
    u = docs["ir-undated-note"]
    assert u.source_published_at is None and u.missing_reason == "feed_item_without_pubdate"  # AC-06


def test_ir_feed_rejects_entity_expansion(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><rss><channel><item><title>&b;</title></item></channel></rss>'
    (tmp_path / "x.test").mkdir()
    (tmp_path / "x.test" / "feed.xml").write_bytes(bomb)
    with pytest.raises(EntitiesForbidden):
        IrFeedSource(
            [Feed("co_x", "https://x.test/feed.xml")], ArchiveTransport(tmp_path), arrival_mode="live"
        ).poll(SINCE)


def test_hash_ignores_whitespace_and_tags() -> None:
    a = content_hash(b"<p>Revenue was  $35.1 billion.</p>\n", "text/html")
    b = content_hash(b"<div>Revenue was $35.1\n billion.</div>", "text/html")
    assert a == b and a != content_hash(b"<p>Revenue was $35.2 billion.</p>", "text/html")


def test_screening() -> None:
    assert screen("NOT FOR PUBLIC RELEASE - draft", "public").visibility == "restricted_review"
    assert screen("normal 8-K text", "public").visibility == "public"
    assert screen("normal", "licensed_internal").visibility == "internal"
    r = screen("normal", "restricted")
    assert r.visibility == "restricted_review" and "license_scope=restricted" in r.reasons
