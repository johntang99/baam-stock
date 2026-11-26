"""DP 1.06 on Postgres: identity keys, merge + independent sources, milestones, analysis versions with an
optimistic lock (AC-08). Data is SYNTHETIC."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
import pytest

from sr.db import ConflictStaleVersion, connect
from sr.events.identity import case_key, deal_key, earnings_key, policy_key, validate
from sr.events.merge import EvidenceIn, Link, attach_evidence, derive_evidence_status
from sr.events.milestones import add_milestone, set_status
from sr.events.versions import publish_analysis, read_state, try_publish
from sr.evidence.ingest import ingest
from sr.evidence.sources.base import RawDocument

T = datetime(2026, 12, 2, 15, 58, 30, tzinfo=UTC)
KEY = "policy:BIS:demo-2026-12345"
README = {
    "event_outcome": {"status": "not_applicable", "reason": "x"},
    "stock_reaction": {"status": "ready", "reason": "y", "allowed_models": ["market_baseline"]},
}


def payload(note: str) -> dict[str, Any]:
    return {
        "analysis_kind": "flash",
        "prediction_readiness": README,
        "evidence_ids": [],
        "market_explanation": {
            "status": "partial",
            "observed_facts": [],
            "possible_drivers": [],
            "counter_evidence": [],
            "unexplained": [note],
        },
    }


def doc(conn, storage, ref: str, text: bytes, source: str = "src_federal_register") -> str:  # type: ignore[no-untyped-def]
    r = ingest(
        conn,
        RawDocument(
            source_id=source,
            external_ref=ref,
            title="synthetic",
            content=text,
            content_type="text/plain",
            received_at=T,
            source_published_at=T,
            source_published_precision="s",
        ),
        now=T + timedelta(seconds=30),
        storage=storage,
    )
    return r.doc_version_id


# ---------------------------------------------------------------- identity (no DB)
def test_identity_keys() -> None:
    assert earnings_key("co_nvda", "fy2027q3") == "earnings:co_nvda:FY2027Q3"
    assert policy_key("bis", "Demo 2026/12345") == "policy:BIS:demo-2026-12345"
    assert case_key("D.Del.", "1:26-cv-00123") == "case:d.del.:1-26-cv-00123"
    assert deal_key("co_a", "co_b", date(2026, 3, 1)) == "deal:co_a:co_b:2026-03-01"
    with pytest.raises(ValueError):
        earnings_key("co_nvda", "Q3 2027")
    with pytest.raises(ValueError):
        validate("random text")


def test_evidence_status_derivation() -> None:
    assert derive_evidence_status([]) == "pending"
    assert derive_evidence_status(["media_report", "primary_confirmed"]) == "primary_confirmed"
    assert derive_evidence_status(["primary_confirmed", "conflicting"]) == "conflicting"
    assert derive_evidence_status(["retracted", "media_report"]) == "media_report"
    assert derive_evidence_status(["retracted"]) == "retracted"


# ---------------------------------------------------------------- merge
def test_merge_rumor_then_confirmation(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    d1 = doc(conn, doc_storage, "wire-a", b"Media report: export rule expected (synthetic)", "src_company_ir")
    d2 = doc(conn, doc_storage, "wire-b", b"Repost of the same media report (synthetic)", "src_company_ir")
    d3 = doc(conn, doc_storage, "fr-12345", b"Federal Register rule text (synthetic)")
    links = [
        Link("sec_nvda", "regulated_party"),
        Link("sec_amd", "regulated_party"),
        Link("sec_mu", "sector_wide"),
    ]
    m1 = attach_evidence(
        conn,
        KEY,
        "policy_export",
        EvidenceIn(d1, "rule expected", {"char_start": 0, "char_end": 12}, "media_report", "origin:wire-a"),
        links,
        now=T,
    )
    m2 = attach_evidence(
        conn,
        KEY,
        "policy_export",
        EvidenceIn(d2, "rule expected", {"char_start": 0, "char_end": 12}, "media_report", "origin:wire-a"),
        links,
        now=T,
    )
    assert m1.created and not m2.created and m1.event_id == m2.event_id
    assert m2.n_independent_origins == 1  # re-publication is not a second source
    assert m2.evidence_status == "media_report"
    m3 = attach_evidence(
        conn,
        KEY,
        "policy_export",
        EvidenceIn(d3, "rule published", {"page": 1}, "primary_confirmed", "origin:fr-12345"),
        now=T,
    )
    assert (
        m3.evidence_status == "primary_confirmed"
        and m3.n_independent_origins == 2
        and m3.row_version == m1.row_version + 1
    )
    m3b = attach_evidence(
        conn,
        KEY,
        "policy_export",
        EvidenceIn(d3, "rule published", {"page": 1}, "primary_confirmed", "origin:fr-12345"),
        now=T,
    )
    assert not m3b.evidence_created and m3b.evidence_id == m3.evidence_id  # idempotent
    assert conn.execute("select count(*) n from event_security_links").fetchone()["n"] == 3
    with pytest.raises(ValueError, match="needs review"):
        attach_evidence(conn, KEY, "litigation_regulatory", EvidenceIn(d3, "x", {}, "pending", "o"), now=T)


def test_milestones(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    d = doc(conn, doc_storage, "fr-1", b"rule (synthetic)")
    ev = attach_evidence(
        conn, KEY, "policy_export", EvidenceIn(d, "c", {}, "primary_confirmed", "o"), now=T
    ).event_id
    m = add_milestone(conn, ev, "rule_effective", expected_at=T + timedelta(days=30), decision_body="BIS")
    with pytest.raises(ValueError):
        set_status(conn, m, "occurred")  # needs actual_at
    set_status(conn, m, "delayed")
    set_status(conn, m, "occurred", actual_at=T + timedelta(days=45))
    with pytest.raises(ValueError):
        set_status(conn, m, "cancelled")  # terminal


# ---------------------------------------------------------------- AC-08 optimistic lock
@pytest.fixture
def event_id(conn, doc_storage) -> str:  # type: ignore[no-untyped-def]
    d = doc(conn, doc_storage, "fr-ac08", b"rule (synthetic)")
    return attach_evidence(
        conn, KEY, "policy_export", EvidenceIn(d, "c", {}, "primary_confirmed", "o"), now=T
    ).event_id


def versions(conn, event_id: str) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    return conn.execute(
        """select analysis_version, analysis_as_of, supersedes_analysis_id, analysis_id,
                                  market_explanation from event_analysis_versions
                           where event_id = %s order by analysis_version""",
        (event_id,),
    ).fetchall()


def test_ac08_old_watermark_cannot_overwrite_new(db_url, conn, event_id) -> None:  # type: ignore[no-untyped-def]
    a, b = connect(db_url, autocommit=True), connect(db_url, autocommit=True)  # two independent workers
    old_asof, new_asof = T + timedelta(minutes=1), T + timedelta(minutes=2)
    snap_a = read_state(a, event_id, "sec_nvda")  # both read the same state
    snap_b = read_state(b, event_id, "sec_nvda")
    assert try_publish(b, snap_b, new_asof, payload("B newer"), new_asof).status == "published"
    with pytest.raises(ConflictStaleVersion):  # A's conditional write fails …
        try_publish(a, snap_a, old_asof, payload("A older"), old_asof)
    r = publish_analysis(a, event_id, "sec_nvda", old_asof, lambda s: payload("A older"), old_asof)
    assert r.status == "discarded"  # … and after re-reading it gives up
    vs = versions(conn, event_id)
    assert len(vs) == 1 and vs[0]["market_explanation"]["unexplained"] == ["B newer"]
    a.close()
    b.close()


def test_ac08_newer_task_retries_on_top(db_url, conn, event_id) -> None:  # type: ignore[no-untyped-def]
    a, b = connect(db_url, autocommit=True), connect(db_url, autocommit=True)
    old_asof, new_asof = T + timedelta(minutes=1), T + timedelta(minutes=2)
    snap_b = read_state(b, event_id, "sec_nvda")  # B (newer input) reads first …
    assert (
        publish_analysis(a, event_id, "sec_nvda", old_asof, lambda s: payload("A"), old_asof).status
        == "published"
    )
    with pytest.raises(ConflictStaleVersion):  # … its stale write is refused …
        try_publish(b, snap_b, new_asof, payload("B"), new_asof)
    r = publish_analysis(b, event_id, "sec_nvda", new_asof, lambda s: payload("B"), new_asof)
    assert r.status == "published" and r.analysis_version == 2  # … and it retries on top of A
    vs = versions(conn, event_id)
    assert [v["analysis_version"] for v in vs] == [1, 2] and vs[1]["supersedes_analysis_id"] == vs[0][
        "analysis_id"
    ]
    cur = conn.execute(
        "select analysis_version from event_analysis_current where event_id = %s", (event_id,)
    ).fetchone()
    assert cur["analysis_version"] == 2
    a.close()
    b.close()


def test_ac08_equal_watermark_is_not_republished(conn, event_id) -> None:  # type: ignore[no-untyped-def]
    t = T + timedelta(minutes=1)
    assert publish_analysis(conn, event_id, "sec_nvda", t, lambda s: payload("x"), t).status == "published"
    assert publish_analysis(conn, event_id, "sec_nvda", t, lambda s: payload("x"), t).status == "discarded"


def test_versions_are_per_security(conn, event_id) -> None:  # type: ignore[no-untyped-def]
    t = T + timedelta(minutes=1)
    assert publish_analysis(conn, event_id, "sec_nvda", t, lambda s: payload("n"), t).analysis_version == 1
    assert publish_analysis(conn, event_id, "sec_amd", t, lambda s: payload("a"), t).analysis_version == 1


def test_db_guards(conn, event_id) -> None:  # type: ignore[no-untyped-def]
    t = T + timedelta(minutes=1)
    publish_analysis(conn, event_id, "sec_nvda", t, lambda s: payload("x"), t)
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("update events set row_version = row_version + 5 where event_id = %s", (event_id,))
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute(
            "update events set row_version = row_version + 1, current_analysis_version = null where event_id = %s",
            (event_id,),
        )
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("update event_analysis_versions set analysis_kind = 'full'")
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("delete from events")
    with pytest.raises(psycopg.errors.CheckViolation):  # version > 1 must supersede something
        conn.execute(
            """insert into event_analysis_versions (analysis_id, event_id, security_id, analysis_version,
                          analysis_kind, analysis_as_of, market_explanation, prediction_readiness)
                        values ('eav_x', %s, 'sec_mu', 2, 'flash', now(), '{}', '{}')""",
            (event_id,),
        )
