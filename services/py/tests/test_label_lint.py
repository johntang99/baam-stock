"""Reviewer self-check for extraction labels (DP 1.18). SYNTHETIC document and labels."""

from sr.evidence.hashing import sha256_text
from sr.llm.labels import DocLabel, GoldFact, lint_label, safe_key

TEXT = "Synthetic Corp (synthetic) reported revenue of $13.4 billion. Data Center revenue was $10.1 billion."


def label(*facts: GoldFact, status: str = "reviewed", by: str = "reviewer-a") -> DocLabel:
    return DocLabel.model_validate(
        {
            "doc_key": "0000000000-26-000001:ex991.htm",
            "text_sha256": sha256_text(TEXT),
            "doc_kind": "earnings_release",
            "label_status": status,
            "labeled_by": by,
            "facts": [f.model_dump() for f in facts],
        }
    )


def gf(**kw: object) -> GoldFact:
    base: dict[str, object] = {
        "metric": "revenue",
        "value": 13.4e9,
        "unit": "USD",
        "period": "FY2027Q3",
        "quote": "reported revenue of $13.4 billion",
    }
    return GoldFact.model_validate({**base, **kw})


def msgs(lab: DocLabel, text: str | None = TEXT) -> list[str]:
    return [
        f"{i.level}:{i.message.split(':')[0]}" for i in lint_label(lab, text, f"{safe_key(lab.doc_key)}.json")
    ]


def test_clean_label_passes() -> None:
    seg = gf(
        value=10.1e9, quote="Data Center revenue was $10.1 billion", segment="Data Center", scope="segment"
    )
    assert lint_label(label(gf(), seg), TEXT) == []


def test_reviewer_mistakes_are_errors() -> None:
    lab = label(
        gf(metric="eps", unit="USD_per_share", value=0.81),  # EPS without basis
        gf(period=None),  # empty period matches anything
        gf(period="Q3 2027", value=13.4e9),
        gf(quote="revenue of $13.4bn"),  # not verbatim
        gf(unit="USD_billion", value=13.4),  # not normalised
        by="prelabel:anthropic/claude-opus-5-5/extract-0.3",
    )
    m = " ".join(msgs(lab))
    for needle in [
        "unknown metric",
        "period is empty",
        "period 'Q3 2027'",
        "not found verbatim",
        "unit 'USD_billion'",
        "reviewed files need labeled_by",
    ]:
        assert needle in m, needle


def test_duplicates_sha_and_missing_document() -> None:
    lab = label(gf(), gf(quote="revenue of $13.4 billion"))
    assert "error:duplicate of fact 0 (same metric/basis/period/segment)" in msgs(lab)
    changed = msgs(lab, TEXT + " edited")
    assert "error:text_sha256 does not match the document" in changed
    assert "error:source document not found locally (run fetch_sec_corpus.py)" in msgs(lab, None)


def test_value_and_scope_warnings() -> None:
    lab = label(
        gf(value=13.4, quote="reported revenue of $13.4 billion"),
        gf(value=99e9, period="FY2027Q2"),
        gf(segment="Data Center", period="FY2027Q1"),
    )
    m = msgs(lab)
    assert "warning:USD value 13.4 looks unscaled (should be whole dollars)" in m
    assert "warning:value 9.9e+10 not seen in the quote at any scale" in m
    assert "warning:segment is set but scope is company" in m
    assert msgs(label(gf(), status="draft", by="prelabel:x")) == []  # drafts may keep the prelabel name
