"""DP 1.04 on Postgres: versions, dedupe, four timestamps, restricted review, point-in-time reads.
AC-06, AC-07, AC-25 (P1), DC §1.1 replay rule. Data is SYNTHETIC."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from sr.evidence.ingest import ingest, ingest_all
from sr.evidence.replay import PointInTimeReader
from sr.evidence.sources.base import RawDocument
from sr.evidence.sources.ir import Feed, IrFeedSource
from sr.evidence.sources.sec import SecEdgarSource
from sr.evidence.sources.transport import ArchiveTransport
from sr.llm.base import PgCallLogger
from sr.llm.fake import FakeLLMProvider
from sr.timeguard import LookaheadError
from tests.conftest import EVIDENCE_ARCHIVE

T = datetime(2026, 11, 19, 21, 0, tzinfo=UTC)
pytestmark = pytest.mark.usefixtures("doc_storage")


def news(
    content: bytes = b"<p>Synthetic Co wins a large order.</p>", ref: str = "wire-1", **kw
) -> RawDocument:  # type: ignore[no-untyped-def]
    base = dict(
        source_id="src_company_ir",
        external_ref=ref,
        title="Order (synthetic)",
        content=content,
        content_type="text/html",
        received_at=T,
        source_published_at=T - timedelta(seconds=30),
        source_published_precision="s",
        subject_company_ids=("co_nvda",),
    )
    return RawDocument(**(base | kw))  # type: ignore[arg-type]


def count(conn, sql: str, *a) -> int:  # type: ignore[no-untyped-def]
    return int(conn.execute(sql, a).fetchone()["n"])


def test_ac06_four_timestamps(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    docs = SecEdgarSource({"0009999001": "co_nvda"}, ArchiveTransport(EVIDENCE_ARCHIVE)).poll(
        T - timedelta(days=30)
    )
    ingest_all(conn, docs, now=T + timedelta(hours=1), storage=doc_storage)
    feed = IrFeedSource(
        [Feed("co_nvda", "https://ir.synthetic.test/feed.xml")], ArchiveTransport(EVIDENCE_ARCHIVE)
    )
    ingest_all(conn, feed.poll(T - timedelta(days=30)), now=T + timedelta(days=2), storage=doc_storage)
    rows = conn.execute("select * from source_document_versions").fetchall()
    assert len(rows) == 5
    for r in rows:
        assert (
            r["received_at"] is not None
            and r["available_at"] is not None
            and r["available_at"] >= r["received_at"]
        )
        assert r["source_published_at"] is not None or r["missing_reason"]  # AC-06
    undated = [r for r in rows if r["source_published_at"] is None]
    assert len(undated) == 1 and undated[0]["missing_reason"] == "feed_item_without_pubdate"
    sec_v = next(r for r in rows if r["locator"] == "sec:0009999001-26-000101")
    assert sec_v["available_at"] == datetime(2026, 11, 19, 21, 21, 5, tzinfo=UTC)  # archived value kept
    assert sec_v["storage_path"] and doc_storage.get(sec_v["storage_path"]).startswith(b"<html>")


def test_missing_published_time_needs_reason(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="missing_reason"):
        ingest(
            conn, news(source_published_at=None, source_published_precision=None), now=T, storage=doc_storage
        )
    with pytest.raises(psycopg.errors.CheckViolation):  # the database enforces it too
        conn.execute("""insert into source_documents (doc_id, source_id, external_ref) values ('doc_x', 'src_company_ir', 'x');
                        insert into source_document_versions (doc_version_id, doc_id, version, content_hash, received_at,
                          available_at, arrival_mode) values ('docv_x', 'doc_x', 1, repeat('a', 64), now(), now(), 'live')""")


def test_ac07_triple_delivery_is_one_version_and_one_job(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    r1 = ingest(conn, news(), now=T, storage=doc_storage)
    r2 = ingest(
        conn, news(received_at=T + timedelta(seconds=5)), now=T + timedelta(seconds=6), storage=doc_storage
    )
    r3 = ingest(
        conn,
        news(content=b"<p>Synthetic Co  wins a large\n order.</p>"),
        now=T + timedelta(seconds=9),
        storage=doc_storage,
    )  # whitespace-only difference
    assert (r1.status, r2.status, r3.status) == ("new", "duplicate", "duplicate")
    assert (
        r1.doc_version_id == r2.doc_version_id == r3.doc_version_id
        and r2.job_id is None
        and r3.job_id is None
    )
    assert count(conn, "select count(*) n from source_document_versions") == 1
    assert count(conn, "select count(*) n from jobs where job_type = 'analyze_event'") == 1
    assert count(conn, "select count(*) n from event_analysis_versions") == 0


def test_correction_creates_new_version(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    v1 = ingest(conn, news(), now=T, storage=doc_storage)
    v2 = ingest(
        conn,
        news(
            content=b"<p>Synthetic Co wins a large order (corrected: two orders).</p>",
            received_at=T + timedelta(hours=1),
        ),
        now=T + timedelta(hours=1),
        storage=doc_storage,
    )
    assert v2.status == "correction" and v2.version == 2 and v2.doc_id == v1.doc_id
    row = conn.execute(
        "select is_correction_of from source_document_versions where doc_version_id = %s",
        (v2.doc_version_id,),
    ).fetchone()
    assert row["is_correction_of"] == v1.doc_version_id
    # replay before the correction sees version 1 only
    assert [r["version"] for r in PointInTimeReader(conn, T + timedelta(minutes=5)).versions()] == [1]
    assert [r["version"] for r in PointInTimeReader(conn, T + timedelta(hours=2)).versions()] == [2]


def test_ac25_restricted_material(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    r = ingest(
        conn,
        news(content=b"<p>NOT FOR PUBLIC RELEASE: draft guidance</p>", ref="leak"),
        now=T,
        storage=doc_storage,
    )
    assert (
        r.visibility == "restricted_review"
        and r.job_id is None
        and "not for public release" in r.screen_reasons
    )
    later = T + timedelta(days=1)
    assert PointInTimeReader(conn, later).versions() == []  # excluded from analysis / features
    with pytest.raises(PermissionError):
        PointInTimeReader(conn, later).version(r.doc_version_id)
    assert len(PointInTimeReader(conn, later, include_restricted=True).versions()) == 1  # admin review only


def test_replay_reads_after_as_of_raise(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    r = ingest(conn, news(), now=T + timedelta(seconds=20), storage=doc_storage)  # available at T+20s
    early = PointInTimeReader(conn, T + timedelta(seconds=10))
    assert early.versions() == []
    with pytest.raises(LookaheadError):
        early.version(r.doc_version_id)
    assert PointInTimeReader(conn, T + timedelta(seconds=20)).version(r.doc_version_id)["version"] == 1


def test_simulated_arrival_uses_simulated_time(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    sim = T + timedelta(minutes=10)
    r = ingest(conn, news(arrival_mode="simulated", simulated_available_at=sim), now=T, storage=doc_storage)
    assert PointInTimeReader(conn, sim - timedelta(seconds=1)).versions() == []
    with pytest.raises(LookaheadError):
        PointInTimeReader(conn, sim - timedelta(seconds=1)).version(r.doc_version_id)
    assert len(PointInTimeReader(conn, sim).versions()) == 1


def test_versions_are_append_only(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    r = ingest(conn, news(), now=T, storage=doc_storage)
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute(
            "update source_document_versions set available_at = now() where doc_version_id = %s",
            (r.doc_version_id,),
        )
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("delete from source_document_versions where doc_version_id = %s", (r.doc_version_id,))
    conn.execute(
        "update source_document_versions set visibility = 'restricted_review' where doc_version_id = %s",
        (r.doc_version_id,),
    )  # compliance may restrict later


def test_unknown_source_rejected(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="unknown source_id"):
        ingest(conn, replace(news(), source_id="src_nope"), now=T, storage=doc_storage)


def test_llm_calls_logged_append_only(conn) -> None:  # type: ignore[no-untyped-def]
    p = FakeLLMProvider(logger=PgCallLogger(conn))
    p.extract_facts("Revenue was $1.0 billion.")
    row = conn.execute("select * from llm_calls").fetchone()
    assert (
        row["purpose"] == "extract_facts"
        and row["status"] == "succeeded"
        and row["request_params"] == {"tools": []}
    )
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("delete from llm_calls")
