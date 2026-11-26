"""DP 1.27 collection log (AC-56) and DP 1.28 reasoning + citations (AC-57, AC-10). SYNTHETIC data."""

from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from sr.events.citations import PgResolver, validate_explanation
from sr.events.merge import EvidenceIn, attach_evidence
from sr.events.reasoning import EvidenceInfo, MarketMove, build, timing
from sr.evidence.classify import categorize, classify, mentions
from sr.evidence.collection_log import counts_from_items, link_items, run_collection
from sr.evidence.sources.base import FetchFailure, RawDocument

# policy day, NVDA 11:30 ET run (AC-56): 2026-12-02 is EST -> 11:30 ET = 16:30Z
ASOF = datetime(2026, 12, 2, 16, 30, tzinfo=UTC)
WINDOW = ASOF - timedelta(minutes=90)


# ---------------------------------------------------------------- classifier (no DB)
def test_mentions_and_categories() -> None:
    assert mentions("NVIDIA and Micron shares fell; AMD flat") == ("co_amd", "co_mu", "co_nvda")
    assert mentions("the word amdahl is not AMD") == ("co_amd",)  # word boundaries
    assert categorize("Revenue for the quarter and fiscal outlook")[0] == "earnings_guidance"
    assert categorize("BIS adds controls on exports, license requirement")[0] == "policy_export"
    assert categorize("nothing relevant here") == ("other", 0.0)


def test_relevance_and_peer_channel() -> None:
    peers = {"co_amd", "co_mu"}
    assert classify("x", "filing", ["co_nvda"], "co_nvda", peers).relevance == 1.0
    c = classify("AMD 8-K", "filing", ["co_amd"], "co_nvda", peers)
    assert c.channel == "peer_company" and c.relevance == 0.5
    assert classify("Bank results", "news", ["co_bank"], "co_nvda", peers).relevance == 0.0
    assert classify("rule", "policy", [], "co_nvda", peers, topic_linked=True).relevance == 0.7


# ---------------------------------------------------------------- AC-56 collection run
class StubSource:
    def __init__(
        self, source_id: str, docs: list[RawDocument], failures: list[FetchFailure] | None = None
    ) -> None:
        self.source_id, self.docs, self.failures = source_id, docs, failures or []

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        return list(self.docs)


class BrokenSource:
    source_id = "src_federal_register"

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        raise ConnectionError("upstream down")


def doc(
    source: str,
    ref: str,
    text: str,
    available: datetime,
    published: datetime | None = None,
    subjects: tuple[str, ...] = (),
) -> RawDocument:
    return RawDocument(
        source_id=source,
        external_ref=ref,
        title=text.split(".")[0],
        content=text.encode(),
        content_type="text/plain",
        received_at=available - timedelta(seconds=5),
        arrival_mode="archived",
        available_at=available,
        source_published_at=published or available - timedelta(seconds=20),
        source_published_precision="s",
        subject_company_ids=subjects,
    )


FLASH = "BIS issues new export license requirement for advanced computing chips; NVIDIA and AMD named."


def scenario(conn) -> tuple[list[Any], dict[str, Any]]:  # type: ignore[no-untyped-def]
    conn.execute("""insert into data_sources (source_id, kind, provider, license_scope, verification_status,
                      time_precision_default) values ('src_news_synthetic', 'news', 'synthetic_wire', 'licensed_internal',
                      'proposed', 's'), ('src_news_synthetic_b', 'news', 'synthetic_wire_b', 'licensed_internal', 'proposed', 's')""")
    t = datetime(2026, 12, 2, 16, 0, tzinfo=UTC)
    news = StubSource(
        "src_news_synthetic",
        [
            doc("src_news_synthetic", "flash-1", FLASH, t + timedelta(seconds=10)),
            doc("src_news_synthetic", "flash-2", FLASH, t + timedelta(seconds=40)),  # repost 1
            doc(
                "src_news_synthetic",
                "late-1",
                "NVIDIA comments on export rule. Revenue impact unclear.",
                ASOF + timedelta(minutes=1),
            ),  # 11:31 ET -> after as_of
            doc("src_news_synthetic", "bank-1", "Regional bank reports deposit inflows. No other news.", t),
            doc("src_news_synthetic", "leak-1", "NOT FOR PUBLIC RELEASE: NVIDIA draft outlook revenue.", t),
        ],
    )
    news_b = StubSource(
        "src_news_synthetic_b",
        [doc("src_news_synthetic_b", "fl-b", FLASH, t + timedelta(seconds=90))],  # repost 2
        [
            FetchFailure(
                "src_news_synthetic_b", "gone-1", "Wire story (removed)", "https://x.test/gone", "HTTPError"
            )
        ],
    )
    sources = [news, news_b, BrokenSource()]
    summary = {
        "source_id": "src_fixture_synthetic",
        "quotes_received": 5400,
        "qualifying_rate": 0.991,
        "sync_success_rate": 0.987,
        "last_quote_ts": ASOF.isoformat(),
    }
    return sources, summary


def test_ac56_collection_items_cover_everything(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    sources, summary = scenario(conn)
    res = run_collection(
        conn, "sec_nvda", sources, WINDOW, ASOF, storage=doc_storage, market_summary=summary, now=ASOF
    )
    items = conn.execute(
        "select * from collection_items where collection_run_id = %s", (res.collection_run_id,)
    ).fetchall()
    by_ref: dict[str, dict[str, Any]] = {}
    for it in items:
        if it["doc_version_id"]:
            ref = conn.execute(
                "select d.external_ref from source_document_versions v join source_documents d using (doc_id) "
                "where v.doc_version_id = %s",
                (it["doc_version_id"],),
            ).fetchone()["external_ref"]
            by_ref[ref] = it
    assert by_ref["flash-1"]["disposition"] == "kept"  # 1 kept + 2 duplicates
    assert by_ref["flash-2"]["disposition"] == "duplicate" and by_ref["fl-b"]["disposition"] == "duplicate"
    assert by_ref["flash-2"]["duplicate_of"] == by_ref["fl-b"]["duplicate_of"] == by_ref["flash-1"]["item_id"]
    assert by_ref["late-1"]["disposition"] == "excluded_after_asof"
    assert by_ref["leak-1"]["disposition"] == "excluded_restricted"
    assert (
        by_ref["leak-1"]["title"].startswith("［受限材料") and by_ref["leak-1"]["snippet"] is None
    )  # placeholder only
    assert (
        by_ref["bank-1"]["disposition"] == "excluded_irrelevant"
        and by_ref["bank-1"]["exclusion_reason"] == "no_mention"
    )
    failed = [i for i in items if i["disposition"] == "fetch_failed"]
    assert len(failed) == 1 and "HTTPError" in failed[0]["exclusion_reason"]
    md = [i for i in items if i["channel"] == "market_data"]
    assert len(md) == 1 and '"qualifying_rate": 0.991' in md[0]["snippet"]  # summary item, not per quote
    for it in items:
        if it["doc_version_id"]:
            assert it["received_at"] and it["available_at"] and it["source_published_at"]  # four timestamps
    run = conn.execute(
        "select * from collection_runs where collection_run_id = %s", (res.collection_run_id,)
    ).fetchone()
    assert run["counts"] == counts_from_items(items)  # counts == items, not hand-filled
    assert run["counts"]["fetched"] == 8 and run["counts"]["kept"] == 2 and run["counts"]["duplicate"] == 2
    polled = {p["source_id"]: p for p in run["sources_polled"]}
    assert (
        polled["src_federal_register"]["status"] == "error"
        and polled["src_news_synthetic_b"]["items_fetched"] == 2
    )
    # channel x category matrix reproducible from the items (what the API returns)
    rows = conn.execute(
        """select channel, category, count(*) n from collection_items where collection_run_id = %s
                           group by 1, 2""",
        (res.collection_run_id,),
    ).fetchall()
    assert {(r["channel"], r["category"]): r["n"] for r in rows} == {
        (ch, cat): n for ch, cats in run["counts"]["matrix"].items() for cat, n in cats.items()
    }


def test_ac56_replay_same_time_same_items(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    sources, summary = scenario(conn)
    a = run_collection(
        conn, "sec_nvda", sources, WINDOW, ASOF, storage=doc_storage, market_summary=summary, now=ASOF
    )
    b = run_collection(
        conn, "sec_nvda", sources, WINDOW, ASOF, storage=doc_storage, market_summary=summary, now=ASOF
    )

    def fingerprint(run_id: str) -> list[tuple[Any, ...]]:
        return sorted(
            (r["doc_version_id"] or "", r["disposition"], r["channel"], r["category"])
            for r in conn.execute(
                "select * from collection_items where collection_run_id = %s", (run_id,)
            ).fetchall()
        )

    assert fingerprint(a.collection_run_id) == fingerprint(b.collection_run_id)
    assert (
        conn.execute("select count(*) n from source_document_versions").fetchone()["n"] == 6
    )  # no new versions


def test_items_are_append_only_except_links(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    sources, _ = scenario(conn)
    res = run_collection(conn, "sec_nvda", sources, WINDOW, ASOF, storage=doc_storage, now=ASOF)
    kept = conn.execute(
        "select * from collection_items where collection_run_id = %s and disposition = 'kept'",
        (res.collection_run_id,),
    ).fetchone()
    ev = attach_evidence(
        conn,
        "policy:BIS:demo-2026-12345",
        "policy_export",
        EvidenceIn(kept["doc_version_id"], "flash", {}, "media_report", "origin:flash"),
        now=ASOF,
    )
    assert link_items(conn, kept["doc_version_id"], ev.event_id, [ev.evidence_id]) >= 1
    row = conn.execute(
        "select linked_event_id, linked_evidence_ids from collection_items where item_id = %s",
        (kept["item_id"],),
    ).fetchone()
    assert row["linked_event_id"] == ev.event_id and row["linked_evidence_ids"] == [ev.evidence_id]
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute(
            "update collection_items set disposition = 'duplicate' where item_id = %s", (kept["item_id"],)
        )
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute(
            "update collection_items set linked_evidence_ids = '{}' where item_id = %s", (kept["item_id"],)
        )
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("delete from collection_items")


# ---------------------------------------------------------------- AC-57 reasoning + citations
MOVE_START = datetime(2026, 12, 2, 16, 0, tzinfo=UTC)  # 11:00 ET: the drop starts


def quotes(conn) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    for qid, ts in (("rq_nvda_before", MOVE_START - timedelta(seconds=1)), ("rq_nvda_asof", ASOF)):
        conn.execute(
            """insert into reference_quotes (quote_id, security_id, quote_ts, received_at, session_type, bid, ask, mid,
                          spread_bp, price_type, is_qualifying, quote_rule_version, vendor_source_id)
                        values (%s, 'sec_nvda', %s, %s, 'regular', 180.0, 180.02, 180.01, 1.1, 'nbbo_mid', true, 'qr-0.1',
                          'src_fixture_synthetic')""",
            (qid, ts, ts),
        )
    return "rq_nvda_before", "rq_nvda_asof"


def evidence_pair(conn, doc_storage) -> tuple[EvidenceInfo, EvidenceInfo, str]:  # type: ignore[no-untyped-def]
    sources, _ = scenario(conn)
    res = run_collection(conn, "sec_nvda", sources, WINDOW, ASOF, storage=doc_storage, now=ASOF)
    kept = conn.execute(
        "select * from collection_items where collection_run_id = %s and disposition = 'kept' "
        "and channel = 'news_wire' order by available_at",
        (res.collection_run_id,),
    ).fetchall()
    out = []
    for i, (it, pub) in enumerate(
        [(kept[0], MOVE_START - timedelta(minutes=1)), (kept[-1], MOVE_START + timedelta(minutes=5))]
    ):
        m = attach_evidence(
            conn,
            "policy:BIS:demo-2026-12345",
            "policy_export",
            EvidenceIn(
                it["doc_version_id"],
                f"claim {i}",
                {},
                "primary_confirmed" if i == 0 else "media_report",
                f"origin:{i}",
            ),
            now=ASOF,
        )
        out.append(
            EvidenceInfo(
                m.evidence_id,
                f"claim {i}",
                pub,
                "s",
                it["available_at"],
                "primary_confirmed" if i == 0 else "media_report",
                (it["item_id"],),
            )
        )
    return out[0], out[1], res.collection_run_id


def test_timing_rules() -> None:
    e = EvidenceInfo(
        "evd",
        "c",
        MOVE_START + timedelta(minutes=1),
        "s",
        MOVE_START + timedelta(minutes=2),
        "primary_confirmed",
    )
    assert timing(e, MOVE_START)[0] == "later"
    assert (
        timing(EvidenceInfo("e", "c", MOVE_START, "day", MOVE_START, "primary_confirmed"), MOVE_START)[0]
        == "imprecise"
    )
    assert (
        timing(
            EvidenceInfo("e", "c", None, None, MOVE_START - timedelta(seconds=1), "media_report"), MOVE_START
        )[0]
        == "earlier"
    )


def test_ac57_reasoning_trace_and_citations(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    before, after = quotes(conn)
    early, late, run_id = evidence_pair(conn, doc_storage)
    move = MarketMove(
        MOVE_START, before, after, stock_return_pct=-1.0, benchmark_return_pct=-3.0
    )  # AC-10 numbers
    drivers = [
        {
            "text": "出口许可要求覆盖部分数据中心 GPU",
            "evidence_ids": [early.evidence_id],
            "quote_ids": [],
            "item_ids": [],
        },
        {
            "text": "后续报道称影响有限",
            "evidence_ids": [late.evidence_id],
            "quote_ids": [],
            "item_ids": [],
        },  # news after the drop
        {"text": "市场担忧（无引用）", "evidence_ids": [], "quote_ids": [], "item_ids": []},
        {"text": "引用不存在的证据", "evidence_ids": ["evd_does_not_exist"], "quote_ids": [], "item_ids": []},
    ]
    counter = [
        {
            "text": "篮子同时下跌 3%，部分属行业共同波动",
            "evidence_ids": [],
            "quote_ids": [before, after],
            "item_ids": [],
        }
    ]
    expl, trace, rejected = build(
        move, [early, late], drivers, counter, PgResolver(conn, run_id), gaps=["收盘价待确认"]
    )

    assert expl["observed_facts"][0]["text"] == "绝对 -1.00%，相对篮子 +2.00pp"  # AC-10: −1% vs −3% -> +2pp
    assert [d["text"] for d in expl["possible_drivers"]] == ["出口许可要求覆盖部分数据中心 GPU"]
    assert any(c["text"] == "后续报道称影响有限" for c in expl["concurrent_events"])  # not a cause (AC-10)
    timing_steps = [s for s in trace if s["kind"] == "timing_check"]
    assert any("不能作为此前走势的原因" in s["conclusion"] for s in timing_steps)
    assert {r["reason"].split(":")[0] for r in rejected} == {"no_citation", "unknown_citation"}
    assert sum("（无引用，校验拒绝，已移入未解释）" in u["text"] for u in expl["unexplained"]) == 2
    for section in ("observed_facts", "possible_drivers", "counter_evidence"):
        for st in expl[section]:
            assert st["evidence_ids"] or st["quote_ids"]  # D-46
            assert (
                isinstance(st["trace_step"], int) and trace[st["trace_step"] - 1]["step"] == st["trace_step"]
            )
    # every cited id resolves to collection_items / reference_quotes / evidence collected in this run
    r = PgResolver(conn, run_id)
    for section in ("observed_facts", "possible_drivers", "counter_evidence"):
        for st in expl[section]:
            assert not r.missing("evidence", st["evidence_ids"]) and not r.missing("quote", st["quote_ids"])
            assert not r.missing("item", st["item_ids"])
    assert trace[0]["kind"] == "market_fact" and trace[-1]["kind"] == "conclusion"
    assert expl["status"] == "partial"  # a valid driver but rejected statements left unexplained residue


def test_removing_a_citation_moves_statement_to_unexplained(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    early, _, run_id = evidence_pair(conn, doc_storage)
    ok = {
        "status": "supported",
        "observed_facts": [],
        "counter_evidence": [],
        "unexplained": [],
        "possible_drivers": [
            {"text": "d", "evidence_ids": [early.evidence_id], "quote_ids": [], "item_ids": []}
        ],
    }
    assert validate_explanation(ok, PgResolver(conn, run_id)).rejected == []
    stripped = {**ok, "possible_drivers": [{**ok["possible_drivers"][0], "evidence_ids": []}]}
    rep = validate_explanation(stripped, PgResolver(conn, run_id))
    assert rep.explanation["possible_drivers"] == [] and rep.rejected[0]["reason"] == "no_citation"
    assert rep.explanation["unexplained"][0]["text"].startswith("d（无引用")
    legacy = {**ok, "possible_drivers": ["plain string driver"]}  # §8.2 legacy strings
    assert validate_explanation(legacy, PgResolver(conn, run_id)).explanation["possible_drivers"] == []


def test_no_market_data_and_no_benchmark(conn) -> None:  # type: ignore[no-untyped-def]
    expl, trace, _ = build(None, [], [], [], PgResolver(conn))
    assert trace[0]["rule"] == "market_data_pending" and expl["status"] == "insufficient"
    before, after = quotes(conn)
    expl2, _, _ = build(
        MarketMove(MOVE_START, before, after, 8.0, None), [], [], [], PgResolver(conn)
    )  # AC-40 shape
    assert "基准不可计算" in expl2["observed_facts"][0]["text"]
