"""AC-41 CEO change: media rumour -> "未经证实" analysis v1; company 8-K -> v2 supersedes v1, evidence primary_confirmed,
both versions replayable (DP 1.25; OQ-55). SYNTHETIC data."""

from datetime import date, time, timedelta

from sr.calendar.calendar import et_to_utc
from sr.events.explain import publish_explanation
from sr.events.merge import EvidenceIn, Link, attach_evidence
from sr.evidence.ingest import ingest
from tests.test_collection_reasoning import doc
from tests.test_reaction_explain import make_quotes, ramp, visible

D = date(2026, 12, 2)
NVDA = "sec_nvda"
PEERS = ["sec_amd", "sec_avgo", "sec_mu"]
W = {p: 1 / 3 for p in PEERS}
KEY = "mgmt:co_nvda:ceo-demo"
RUMOUR, FILING = et_to_utc(D, time(10, 10)), et_to_utc(D, time(11, 0))


def quotes(as_of):  # type: ignore[no-untyped-def]
    start = et_to_utc(D, time(9, 30))
    paths = {NVDA: ramp(100, 97, RUMOUR + timedelta(minutes=1), RUMOUR + timedelta(minutes=20))}
    paths |= {p: ramp(50, 50, start, start + timedelta(seconds=1)) for p in PEERS}
    return visible(make_quotes(paths, start, as_of), as_of)


def test_ac41_rumour_then_confirmation(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    conn.execute("""insert into data_sources (source_id, kind, provider, license_scope, verification_status, time_precision_default)
                    values ('src_news_synthetic', 'news', 'synthetic_wire', 'licensed_internal', 'proposed', 's')""")
    r1 = ingest(
        conn,
        doc(
            "src_news_synthetic",
            "rumour-1",
            "Report: NVIDIA CEO may step down (synthetic).",
            RUMOUR + timedelta(seconds=20),
            published=RUMOUR,
            subjects=("co_nvda",),
        ),
        now=RUMOUR + timedelta(seconds=20),
        storage=doc_storage,
    )
    m1 = attach_evidence(
        conn,
        KEY,
        "executive_change",
        EvidenceIn(r1.doc_version_id, "CEO may step down (media, synthetic)", {}, "media_report", "wire-1"),
        links=[Link(NVDA, "subject")],
        now=RUMOUR + timedelta(seconds=30),
    )
    assert m1.evidence_status == "media_report"

    t1 = et_to_utc(D, time(10, 40))
    v1 = publish_explanation(conn, m1.event_id, NVDA, t1, t1 + timedelta(seconds=5), quotes(t1), weights=W)
    row1 = conn.execute(
        "select * from event_analysis_versions where analysis_id = %s", (v1.publish.analysis_id,)
    ).fetchone()
    assert any(
        u["text"].startswith("未经证实") for u in row1["market_explanation"]["unexplained"]
    )  # AC-41: marked unconfirmed
    assert "unconfirmed_evidence" in row1["data_gaps"]
    assert not any(
        "CEO may step down" in f["text"] for f in row1["market_explanation"]["observed_facts"]
    )  # not a fact

    # the company's 8-K confirms it
    r2 = ingest(
        conn,
        doc(
            "src_sec_edgar",
            "8k-ceo-1",
            "Form 8-K Item 5.02: CEO transition (synthetic).",
            FILING + timedelta(seconds=30),
            published=FILING,
            subjects=("co_nvda",),
        ),
        now=FILING + timedelta(seconds=30),
        storage=doc_storage,
    )
    m2 = attach_evidence(
        conn,
        KEY,
        "executive_change",
        EvidenceIn(
            r2.doc_version_id, "CEO transition announced in 8-K (synthetic)", {}, "primary_confirmed", "8k-1"
        ),
        links=[Link(NVDA, "subject")],
        now=FILING + timedelta(minutes=1),
    )
    assert m2.event_id == m1.event_id and m2.evidence_status == "primary_confirmed"

    t2 = et_to_utc(D, time(11, 20))
    v2 = publish_explanation(conn, m2.event_id, NVDA, t2, t2 + timedelta(seconds=5), quotes(t2), weights=W)
    row2 = conn.execute(
        "select * from event_analysis_versions where analysis_id = %s", (v2.publish.analysis_id,)
    ).fetchone()
    assert row2["analysis_version"] == 2 and row2["supersedes_analysis_id"] == v1.publish.analysis_id
    assert not any(u["text"].startswith("未经证实") for u in row2["market_explanation"]["unexplained"])
    assert "unconfirmed_evidence" not in row2["data_gaps"]
    assert any("8-K" in f["text"] for f in row2["market_explanation"]["observed_facts"])  # confirmed fact
    ev = conn.execute("select evidence_status from events where event_id = %s", (m2.event_id,)).fetchone()
    assert ev["evidence_status"] == "primary_confirmed"

    # both versions are kept and replayable: v1 is exactly as it was, each with its own reasoning trace
    again = conn.execute(
        "select * from event_analysis_versions where analysis_id = %s", (v1.publish.analysis_id,)
    ).fetchone()
    assert (
        again["market_explanation"] == row1["market_explanation"]
        and again["reasoning_trace"] == row1["reasoning_trace"]
    )
    assert row1["reasoning_trace"] and row2["reasoning_trace"]
    assert row1["analysis_as_of"] < row2["analysis_as_of"]
