"""DP 2.04 live evidence polling (OQ-60) and DP 2.05 per-security impact records (OQ-61). SYNTHETIC documents."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from sr.calendar.calendar import et_to_utc
from sr.events.exposure import impact_for, read_through_links
from sr.events.merge import EvidenceIn, Link, attach_evidence
from sr.evidence.live import LicensedNewsSource, LivePoller, SourceDisabled
from sr.evidence.sources.base import RawDocument

T = datetime(2026, 12, 1, 15, 0, tzinfo=UTC)


class Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t


class FakeSource:
    """Releases synthetic press releases at their publication time; can be switched to failing."""

    def __init__(self, source_id: str, clock: Clock, releases: list[tuple[datetime, str, str]]) -> None:
        self.source_id, self.clock, self.releases = source_id, clock, releases
        self.calls: list[datetime] = []
        self.down = False

    def poll(self, since_utc: datetime) -> list[RawDocument]:
        self.calls.append(since_utc)
        if self.down:
            raise ConnectionError("source unreachable")
        now = self.clock()
        return [
            RawDocument(
                source_id=self.source_id,
                external_ref=ref,
                title=f"{ref} (synthetic)",
                content=f"<p>{text}</p>".encode(),
                content_type="text/html",
                received_at=now,
                source_published_at=at,
                source_published_precision="s",
                subject_company_ids=(f"co_{ref.split('-')[0]}",),
            )
            for at, ref, text in self.releases
            if since_utc < at <= now
        ]


def test_poller_cadence_dedupe_and_analysis_jobs(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    clock = Clock(T)
    src = FakeSource("src_company_ir", clock, [(T - timedelta(seconds=60), "amd-order-1", "Synthetic order")])
    p = LivePoller(conn, [src], clock, storage=doc_storage)
    (r,) = p.poll_due()
    assert r.status == "ok" and [x.status for x in r.results] == ["new"]
    clock.t = T + timedelta(seconds=30)
    assert p.poll_due() == []  # company IR cadence is 60 s
    clock.t = T + timedelta(seconds=61)
    (r2,) = p.poll_due()  # the overlap re-delivers the same item: a duplicate, no new version
    assert [x.status for x in r2.results] == ["duplicate"]
    assert src.calls[1] == T - timedelta(seconds=120)  # since = last success - overlap
    jobs = conn.execute("select job_type, run_after from jobs").fetchall()
    assert [j["job_type"] for j in jobs] == ["analyze_event"]
    v = conn.execute(
        "select received_at, available_at, arrival_mode from source_document_versions"
    ).fetchone()
    assert v["arrival_mode"] == "live" and v["available_at"] >= v["received_at"]


def test_failed_poll_is_a_failure_not_no_news(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    clock = Clock(T)
    src = FakeSource("src_company_ir", clock, [])
    src.down = True
    p = LivePoller(conn, [src], clock, storage=doc_storage)
    (r,) = p.poll_due()
    assert r.status == "failed" and "unreachable" in (r.error or "")
    clock.t = T + timedelta(seconds=20)
    assert p.poll_due() == []  # backoff 30 s
    clock.t = T + timedelta(seconds=31)
    assert p.poll_due()[0].status == "failed"
    st = p.summary()["src_company_ir"]
    assert st["consecutive_failures"] == 2 and st["last_success_at"] is None
    clock.t = T + timedelta(seconds=200)
    src.down = False
    assert p.poll_due()[0].status == "ok" and p.summary()["src_company_ir"]["consecutive_failures"] == 0


def test_licensed_news_stays_disabled(conn) -> None:  # type: ignore[no-untyped-def]
    news = LicensedNewsSource()
    assert news.enabled is False
    with pytest.raises(SourceDisabled):
        news.poll(T)
    p = LivePoller(conn, [news], Clock(T))
    assert [r.status for r in p.poll_due()] == ["disabled"]
    assert p.poll_due() == []  # recorded once, never polled


# ---------------------------------------------------------------- DP 2.05: one event, independent records
def _amd_order(conn, doc_storage, at: datetime) -> str:  # type: ignore[no-untyped-def]
    from sr.evidence.ingest import ingest

    clock = Clock(at)
    raw = FakeSource("src_company_ir", clock, [(at - timedelta(seconds=30), "amd-order-2", "AMD wins order")])
    res = ingest(conn, raw.poll(at - timedelta(minutes=5))[0], at, doc_storage)
    m = attach_evidence(
        conn,
        "deal:amd-order-2",
        "customer_demand",
        EvidenceIn(
            res.doc_version_id,
            "AMD announces a large accelerator order (synthetic)",
            {},
            "primary_confirmed",
            "o:amd2",
        ),
        links=[Link("sec_amd", "subject")],
        now=at,
    )
    return m.event_id


def test_read_through_links_follow_the_profiles(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    ev = _amd_order(conn, doc_storage, T)
    got = {lk.security_id: lk.relation for lk in read_through_links(conn, ev, T)}
    assert got == {"sec_nvda": "competitor", "sec_mu": "supplier"}  # AVGO: no relation, no link
    assert read_through_links(conn, ev, T) == []  # idempotent
    rel = {
        r["security_id"]: r["relation"]
        for r in conn.execute(
            "select security_id, relation from event_security_links where event_id = %s", (ev,)
        )
    }
    assert rel == {"sec_amd": "subject", "sec_nvda": "competitor", "sec_mu": "supplier"}


def test_profiles_are_point_in_time(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    before = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)  # only profile v1 (no relations) was in force
    ev = _amd_order(conn, doc_storage, before)
    assert read_through_links(conn, ev, before) == []


def test_same_event_gives_separate_impact_records(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    from sr.events.explain import publish_explanation
    from tests.test_reaction_explain import make_quotes, ramp

    at = et_to_utc(date(2026, 12, 1), time(11, 0))
    ev = _amd_order(conn, doc_storage, at - timedelta(minutes=2))
    read_through_links(conn, ev, at)
    peers = ["sec_qcom", "sec_txn", "sec_intc"]
    w = {p: 1 / 3 for p in peers}
    out = {}
    for sec in ("sec_amd", "sec_nvda"):
        q = make_quotes(
            {sec: ramp(100, 101, at - timedelta(minutes=5), at), **{p: ramp(50, 50, at, at) for p in peers}},
            at - timedelta(minutes=25),
            at,
        )
        q = q[q["received_at"] <= at].reset_index(drop=True)
        r = publish_explanation(conn, ev, sec, at, at + timedelta(seconds=1), q, weights=w)
        out[sec] = conn.execute(
            "select impact from event_analysis_versions where analysis_id = %s", (r.publish.analysis_id,)
        ).fetchone()["impact"]
    amd, nvda = out["sec_amd"], out["sec_nvda"]
    assert amd[0]["channel"] == "direct" and amd[0]["relation"] == "subject"
    assert nvda[0]["channel"] == "competitive_read_through" and "sec_amd" in nvda[0]["exposure"]
    assert amd[0]["exposure"] != nvda[0]["exposure"]
    assert {i["direction"] for i in amd + nvda} == {"unknown"}  # no keyword-guessed direction (S2)
    assert impact_for(conn, ev, "sec_avgo", ["x"], []) == []  # not linked: no record
