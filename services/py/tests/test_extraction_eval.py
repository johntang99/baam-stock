"""DP 1.18 extraction evaluation set: corpus fetch (offline archive), scoring, D-32 gate (AC-30). SYNTHETIC data."""

import json
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from sr.config import load
from sr.events.earnings import process_earnings_document
from sr.events.factcheck import check_facts
from sr.evidence.hashing import normalized_text
from sr.evidence.ingest import ingest
from sr.evidence.sources.base import RawDocument
from sr.features.llm_gate import PromptNotApproved, event_feature_inputs, require_approved
from sr.llm.base import ExtractedFact
from sr.llm.eval_extraction import label_scores, match, run_eval, save_report
from sr.llm.fake import FakeLLMProvider
from sr.llm.labels import DocLabel, GoldFact, read_labels, read_manifest, write_label
from tests.conftest import EVIDENCE_ARCHIVE

EX991 = EVIDENCE_ARCHIVE / "www.sec.gov/Archives/edgar/data/9999001/000999900126000201/ex991.htm"
ACC = "0009999001-26-000201"


# ---------------------------------------------------------------- corpus fetch (synthetic archive, no network)
@pytest.fixture
def archive(tmp_path: Path) -> Path:
    root = tmp_path / "archive"
    (root / "www.sec.gov/files").mkdir(parents=True)
    (root / "www.sec.gov/files/company_tickers.json").write_text(
        json.dumps({"0": {"cik_str": 9999001, "ticker": "NVDA", "title": "SYNTHETIC SEMICONDUCTOR CO"}})
    )
    (root / "data.sec.gov/submissions").mkdir(parents=True)
    (root / "data.sec.gov/submissions/CIK0009999001.json").write_text(
        json.dumps(
            {
                "filings": {
                    "recent": {
                        "accessionNumber": [ACC, "0009999001-26-000102", "0009999001-21-000001"],
                        "form": ["8-K", "10-Q", "8-K"],
                        "filingDate": ["2026-11-19", "2026-11-19", "2021-02-01"],
                        "acceptanceDateTime": ["2026-11-19T16:20:31.000Z"] * 3,
                        "primaryDocument": ["form8k.htm", "form10q.htm", "old.htm"],
                    }
                }
            }
        )
    )
    d = root / "www.sec.gov/Archives/edgar/data/9999001/000999900126000201"
    d.mkdir(parents=True)
    (d / "index.json").write_text(
        json.dumps(
            {
                "directory": {
                    "item": [
                        {"name": "form8k.htm"},
                        {"name": "ex991.htm"},
                        {"name": "R1.htm"},
                        {"name": "Financial_Report.xlsx"},
                    ]
                }
            }
        )
    )
    shutil.copy(EX991, d / "ex991.htm")
    (d / "form8k.htm").write_text("<html><body>Item 2.02 Results of Operations (synthetic).</body></html>")
    return root


def add_index_html(root: Path) -> None:
    """Issuer-specific exhibit names (like NVIDIA's q3fy25pr.htm) are found by declared type, not by name."""
    d = root / "www.sec.gov/Archives/edgar/data/9999001/000999900126000201"
    (d / f"{ACC}-index.htm").write_text(
        "<table><tr><th>Seq</th></tr>"
        "<tr><td>1</td><td>8-K</td><td><a>form8k.htm</a> &nbsp;iXBRL</td><td>8-K</td><td>1</td></tr>"
        "<tr><td>2</td><td>EX-99.1</td><td><a>q3fy27pr.htm</a></td><td>EX-99.1</td><td>2</td></tr>"
        "<tr><td>3</td><td>EX-99.2</td><td><a>q3fy27cfo.htm</a></td><td>EX-99.2</td><td>3</td></tr>"
        "<tr><td>4</td><td>LOGO</td><td><a>logo.jpg</a></td><td>GRAPHIC</td><td>4</td></tr></table>"
    )
    shutil.copy(EX991, d / "q3fy27pr.htm")
    (d / "q3fy27cfo.htm").write_text(
        "<html><body>CFO commentary: revenue was $35.1 billion (synthetic).</body></html>"
    )


def fetch(archive: Path, tmp: Path) -> tuple[int, Path, Path]:
    from tests.conftest import _load_script

    mod = _load_script("fetch_sec_corpus")
    from sr.evidence.sources.transport import ArchiveTransport

    corpus, labels = tmp / "corpus", tmp / "labels"
    n = mod.fetch(ArchiveTransport(archive), ["NVDA"], date(2023, 1, 1), 30, corpus, labels)
    return n, corpus, labels


def test_fetch_corpus_from_archive(archive: Path, tmp_path: Path) -> None:
    n, corpus, labels = fetch(archive, tmp_path)
    man = read_manifest(labels)
    assert n == 2 and set(man) == {f"{ACC}:ex991.htm", f"{ACC}:form8k.htm"}  # 10-Q, old, R1, xlsx skipped
    row = man[f"{ACC}:ex991.htm"]
    assert row["file_kind"] == "ex99" and row["cik"] == "0009999001" and (corpus / row["path"]).exists()
    assert (
        row["sha256_text"]
        == __import__("hashlib").sha256(normalized_text(EX991.read_bytes(), "text/html").encode()).hexdigest()
    )
    n2, _, _ = fetch(archive, tmp_path)
    assert n2 == 0  # idempotent


def test_exhibits_found_by_declared_type(archive: Path, tmp_path: Path) -> None:
    add_index_html(archive)
    n, _, labels = fetch(archive, tmp_path)
    man = read_manifest(labels)
    assert set(man) == {f"{ACC}:q3fy27pr.htm", f"{ACC}:q3fy27cfo.htm", f"{ACC}:form8k.htm"}  # logo skipped
    assert {man[k]["file_kind"] for k in man} == {"ex99", "primary"} and n == 3


def test_unknown_ticker(archive: Path, tmp_path: Path) -> None:
    from sr.evidence.sources.transport import ArchiveTransport
    from tests.conftest import _load_script

    with pytest.raises(KeyError):
        _load_script("fetch_sec_corpus").resolve_ciks(ArchiveTransport(archive), ["ZZZZ"])


# ---------------------------------------------------------------- scoring maths
def cf(metric: str, value: float, period: str = "FY2027Q3", direction: str | None = None) -> Any:
    q = f"{metric} was ${value}"  # quote must contain the value, or the fact checker rejects it
    f = ExtractedFact(
        metric, value, "USD", None, period, None, q, {"char_start": 0, "char_end": len(q)}, direction
    )
    return check_facts((f,), None).accepted[0]


def test_match_and_label_scores() -> None:
    gold = [
        GoldFact(metric="revenue", value=1.0, unit="USD", period="FY2027Q3", quote="q", direction="increase"),
        GoldFact(
            metric="net_income", value=2.0, unit="USD", period="FY2027Q3", quote="q", direction="decrease"
        ),
        GoldFact(metric="revenue_outlook", value=3.0, unit="USD", period="FY2027Q4", quote="q"),
    ]
    pred = [
        cf("revenue", 1.0, direction="increase"),
        cf("net income", 2.0, direction="increase"),
        cf("revenue", 9.0),
    ]
    pairs = match(pred, gold, 1e-6)
    assert [(p.metric, g.metric) for p, g in pairs] == [("revenue", "revenue"), ("net_income", "net_income")]
    s = label_scores([(p.direction, g.direction) for p, g in pairs])
    # classes increase (P=1/2, R=1) and decrease (P=0, R=0) -> macro P=0.25, R=0.5
    assert (s.precision, s.recall) == (0.25, 0.5) and s.f1 == pytest.approx(1 / 3)


def test_rounded_prediction_matches_exact_gold() -> None:
    """OQ-42: "$16.0 billion" is the exact 15,955M rounded; it matches only when rounded matching is on."""
    gold = [GoldFact(metric="operating_income", value=15_955e6, unit="USD", period="FY2026Q3", quote="q")]
    rounded = ExtractedFact(
        "operating_income",
        16.0,
        "USD_billion",
        None,
        "FY2026Q3",
        None,
        "operating income of $16.0 billion (synthetic)",
        {},
    )
    pred = check_facts((rounded,), None).accepted
    assert match(pred, gold, 1e-6) == []  # exact matching only
    assert len(match(pred, gold, 1e-6, min_sig=2)) == 1
    assert match(pred, gold, 1e-6, min_sig=4) == []  # 16.0 is stored as 16: 2 sig. figures


def test_too_coarse_or_wrong_rounding_does_not_match() -> None:
    gold = [GoldFact(metric="revenue", value=13.4e9, unit="USD", period="FY2026Q3", quote="q")]
    for value, quote in [
        (10.0, "revenue of $10 billion (synthetic)"),
        (13.5, "revenue of $13.5 billion (synthetic)"),
    ]:
        f = ExtractedFact("revenue", value, "USD_billion", None, "FY2026Q3", None, quote, {})
        assert match(check_facts((f,), None).accepted, gold, 1e-6, min_sig=2) == [], value


# ---------------------------------------------------------------- evaluation end to end
GOLD = [
    GoldFact(
        metric="revenue",
        value=35.1e9,
        unit="USD",
        period="FY2027Q3",
        quote="Revenue for the quarter was $35.1 billion",
        direction="increase",
    ),
    GoldFact(
        metric="eps_gaap",
        value=0.79,
        unit="USD_per_share",
        period="FY2027Q3",
        basis="gaap",
        quote="GAAP earnings per diluted share for the quarter were $0.79",
    ),
    GoldFact(
        metric="eps_non_gaap",
        value=0.81,
        unit="USD_per_share",
        period="FY2027Q3",
        basis="non_gaap",
        quote="Non-GAAP earnings per diluted share for the quarter were $0.81",
    ),
    GoldFact(
        metric="gross_margin_pct",
        value=74.6,
        unit="pct",
        period="FY2027Q3",
        basis="gaap",
        quote="GAAP gross margin was 74.6%",
    ),
    GoldFact(
        metric="revenue_outlook",
        value=37.5e9,
        unit="USD",
        period="FY2027Q4",
        quote="Revenue is expected to be $37.5 billion",
        certainty="guidance",
    ),
]
PERFECT = [  # what a correct extract-0.2 model output looks like for ex991
    {
        "metric": "revenue",
        "value": 35.1,
        "unit": "USD_billion",
        "currency": "USD",
        "period": "third quarter of fiscal 2027",
        "basis": None,
        "quote": "Revenue for the quarter was $35.1 billion",
        "direction": "increase",
        "scope": "company",
        "certainty": "reported",
    },
    {
        "metric": "eps",
        "value": 0.79,
        "unit": "USD_per_share",
        "currency": "USD",
        "period": None,
        "basis": "gaap",
        "quote": "GAAP earnings per diluted share for the quarter were $0.79",
        "direction": "none",
        "scope": "company",
        "certainty": "reported",
    },
    {
        "metric": "eps",
        "value": 0.81,
        "unit": "USD_per_share",
        "currency": "USD",
        "period": None,
        "basis": "non_gaap",
        "quote": "Non-GAAP earnings per diluted share for the quarter were $0.81",
        "direction": "none",
        "scope": "company",
        "certainty": "reported",
    },
    {
        "metric": "gross margin",
        "value": 74.6,
        "unit": "pct",
        "currency": None,
        "period": None,
        "basis": "gaap",
        "quote": "GAAP gross margin was 74.6%",
        "direction": "none",
        "scope": "company",
        "certainty": "reported",
    },
    {
        "metric": "revenue outlook",
        "value": 37.5,
        "unit": "USD_billion",
        "currency": "USD",
        "period": "fourth quarter of fiscal 2027",
        "basis": None,
        "quote": "Revenue is expected to be $37.5 billion",
        "direction": "none",
        "scope": "company",
        "certainty": "guidance",
    },
]


@pytest.fixture
def gold_set(archive: Path, tmp_path: Path) -> tuple[Path, Path]:
    _, corpus, labels = fetch(archive, tmp_path)
    sha = read_manifest(labels)[f"{ACC}:ex991.htm"]["sha256_text"]
    write_label(
        DocLabel(
            doc_key=f"{ACC}:ex991.htm",
            text_sha256=str(sha),
            doc_kind="earnings_release",
            fiscal_period="FY2027Q3",
            label_status="reviewed",
            labeled_by="analyst-a",
            facts=GOLD,
        ),
        labels,
    )
    write_label(
        DocLabel(
            doc_key=f"{ACC}:form8k.htm",
            text_sha256=str(read_manifest(labels)[f"{ACC}:form8k.htm"]["sha256_text"]),
            doc_kind="8k_other",
            label_status="draft",
            labeled_by="prelabel:fake",
            facts=[],
        ),
        labels,
    )
    return corpus, labels


def perfect_provider() -> FakeLLMProvider:
    p = FakeLLMProvider()
    p.model = "perfect-0.1"
    p.register(normalized_text(EX991.read_bytes(), "text/html"), PERFECT)
    return p


def test_fake_provider_fails_direction_gate(gold_set: tuple[Path, Path]) -> None:
    corpus, labels = gold_set
    assert [x.doc_key for x in read_labels(labels)] == [f"{ACC}:ex991.htm"]  # drafts never count
    rep = run_eval(FakeLLMProvider(), labels_root=labels, corpus_root=corpus)
    assert rep.n_docs == 1 and rep.prompt_version == load("llm")["prompts"]["extract_facts"]
    assert rep.scores["numeric_fact"].precision == 1.0 and rep.scores["numeric_fact"].recall == pytest.approx(
        0.4
    )
    assert rep.passed["numeric_fact"] and not rep.passed["direction"]  # regex has no direction


def test_perfect_provider_passes(gold_set: tuple[Path, Path]) -> None:
    corpus, labels = gold_set
    rep = run_eval(perfect_provider(), labels_root=labels, corpus_root=corpus)
    assert rep.scores["numeric_fact"].precision == rep.scores["numeric_fact"].recall == 1.0
    assert rep.scores["direction"].f1 == 1.0 and all(rep.passed.values())


def test_changed_document_text_is_detected(gold_set: tuple[Path, Path]) -> None:
    corpus, labels = gold_set
    path = corpus / str(read_manifest(labels)[f"{ACC}:ex991.htm"]["path"])
    path.write_text(path.read_text().replace("74.6%", "74.7%"))
    with pytest.raises(ValueError, match="sha mismatch"):
        run_eval(FakeLLMProvider(), labels_root=labels, corpus_root=corpus)


# ---------------------------------------------------------------- AC-30 gate (Postgres)
def test_ac30_gate(conn, gold_set, doc_storage, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    corpus, labels = gold_set
    fake = FakeLLMProvider()
    with pytest.raises(PromptNotApproved, match="no evaluation run"):
        require_approved(conn, fake.provider, fake.model, fake.version)
    ids = save_report(conn, run_eval(fake, labels_root=labels, corpus_root=corpus))
    assert len(ids) == 4 and conn.execute("select count(*) n from extraction_eval_runs").fetchone()["n"] == 4
    with pytest.raises(PromptNotApproved, match="direction: below D-32 threshold"):
        require_approved(conn, fake.provider, fake.model, fake.version)

    # feature building refuses facts extracted by the unapproved prompt (negative test)
    t = datetime(2026, 11, 19, 21, 21, 5, tzinfo=UTC)
    dv = ingest(
        conn,
        RawDocument(
            source_id="src_sec_edgar",
            external_ref=ACC,
            title="EX-99.1",
            content=EX991.read_bytes(),
            content_type="text/html",
            received_at=t,
            source_published_at=t - timedelta(seconds=30),
            source_published_precision="s",
        ),
        now=t,
        storage=doc_storage,
    ).doc_version_id
    fake_for_pipeline = FakeLLMProvider()
    fake_for_pipeline.register(normalized_text(EX991.read_bytes(), "text/html"), PERFECT)
    out = process_earnings_document(
        conn,
        dv,
        "co_nvda",
        "sec_nvda",
        "FY2027Q3",
        fake_for_pipeline,
        [],
        t + timedelta(minutes=1),
        t + timedelta(minutes=1),
        storage=doc_storage,
    )
    aid = out.published[0].analysis_id
    assert aid is not None
    with pytest.raises(PromptNotApproved):
        event_feature_inputs(conn, aid)

    # a passing prompt still needs enough reviewed documents …
    perfect = perfect_provider()
    save_report(conn, run_eval(perfect, labels_root=labels, corpus_root=corpus))
    with pytest.raises(PromptNotApproved, match="only 1 reviewed documents"):
        require_approved(conn, perfect.provider, perfect.model, perfect.version)
    # … and is approved once the minimum is met
    monkeypatch.setitem(load("extraction_eval")["approval"], "min_reviewed_docs", 1)
    require_approved(conn, perfect.provider, perfect.model, perfect.version)
