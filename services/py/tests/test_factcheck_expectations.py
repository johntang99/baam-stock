"""DP 1.07 pure logic: deterministic fact checks and expectation comparison (AC-09). SYNTHETIC values."""

from datetime import UTC, datetime, timedelta

import pydantic
import pytest

from sr.events.expectations import compare
from sr.events.factcheck import canonical_metric, check_facts, normalize_period
from sr.llm.base import ExtractedFact

DISCLOSED = datetime(2026, 11, 19, 21, 20, 31, tzinfo=UTC)  # 16:20:31 ET
ASOF = DISCLOSED + timedelta(minutes=5)


def fact(
    metric: str,
    value: float | None,
    unit: str,
    quote: str,
    basis: str | None = None,
    period: str | None = None,
) -> ExtractedFact:
    return ExtractedFact(
        metric, value, unit, None, period, basis, quote, {"char_start": 0, "char_end": len(quote)}
    )


def test_canonical_metrics_and_eps_basis() -> None:
    assert canonical_metric("Earnings per diluted share", "non_gaap") == ("eps_non_gaap", "")
    assert canonical_metric("EPS", "gaap") == ("eps_gaap", "")
    assert canonical_metric("diluted EPS", None) == (None, "basis_not_stated")  # AC-09: never mix bases
    assert canonical_metric("Total Revenue", None) == ("revenue", "")
    assert canonical_metric("headcount", None) == (None, "unknown_metric")


def test_period_normalisation() -> None:
    assert normalize_period("third quarter of fiscal 2027") == "FY2027Q3"
    assert normalize_period("Q4 FY2027") == "FY2027Q4"
    assert normalize_period("FY2027 Q1") == "FY2027Q1"
    assert normalize_period("next year") is None
    assert normalize_period("third quarter of 2026") == "FY2026Q3"  # calendar-year issuers (AMD)
    assert normalize_period("Q3 2026") == "FY2026Q3" and normalize_period("Q4'2026") == "FY2026Q4"
    assert normalize_period("fourth fiscal quarter of 2026") == "FY2026Q4"
    assert normalize_period("fiscal 2026") == "FY2026" and normalize_period("full-year 2026") == "FY2026"
    assert normalize_period("2026") is None  # bare year is ambiguous


def test_value_scale_unit_checks() -> None:
    rep = check_facts(
        (
            fact("revenue", 35.1, "USD_billion", "Revenue for the quarter was $35.1 billion"),
            fact("eps", 0.81, "USD_per_share", "Non-GAAP earnings per diluted share were $0.81", "non_gaap"),
            fact(
                "eps", 0.18, "USD_per_share", "GAAP earnings per diluted share were $0.79", "gaap"
            ),  # value not in quote
            fact("net income", 9.0, "USD_billion", "Net income was $9.0 million"),  # scale mismatch
            fact("gross margin", 174.6, "pct", "gross margin was 174.6%", "gaap"),  # out of range
            fact("eps", 0.81, "USD_per_share", "EPS was $0.81"),  # no basis
        ),
        "FY2027Q3",
    )
    acc = {f.metric: f for f in rep.accepted}
    assert set(acc) == {"revenue", "eps_non_gaap"}
    assert (
        acc["revenue"].value == pytest.approx(35.1e9)
        and acc["revenue"].unit == "USD"
        and acc["revenue"].period == "FY2027Q3"
    )
    assert {r["reason"] for r in rep.rejected} == {
        "value_not_in_quote",
        "pct_out_of_range",
        "basis_not_stated",
    }
    assert len(rep.rejected) == 4 and all(g.startswith("fact_check_failed:") for g in rep.gaps)


def test_conflicting_values_are_withheld() -> None:
    rep = check_facts(
        (
            fact("revenue", 35.1, "USD_billion", "Revenue was $35.1 billion"),
            fact("revenue", 35.2, "USD_billion", "revenue of $35.2 billion"),
            fact("revenue", 35.1, "USD_billion", "Revenue was $35.1 billion"),
        ),
        "FY2027Q3",
    )
    assert rep.accepted == [] and rep.rejected[0]["reason"] == "conflicting_values"


def snap(
    value: float,
    as_of: datetime,
    metric: str = "eps_non_gaap",
    basis: str = "non_gaap",
    precision: str = "s",
    available: datetime | None = None,
    exp_id: str = "exp_1",
) -> dict:
    return {
        "exp_id": exp_id,
        "company_id": "co_nvda",
        "metric": metric,
        "fiscal_period": "FY2027Q3",
        "value": value,
        "unit": "USD_per_share",
        "accounting_basis": basis,
        "expectation_type": "analyst_consensus",
        "snapshot_as_of": as_of.isoformat().replace("+00:00", "Z"),
        "snapshot_precision": precision,
        "available_at": (available or as_of).isoformat().replace("+00:00", "Z"),
        "source_id": "src_synthetic",
    }


EPS = check_facts(
    (fact("eps", 0.81, "USD_per_share", "Non-GAAP EPS were $0.81", "non_gaap"),), "FY2027Q3"
).accepted[0]


def test_ac09_only_post_event_consensus() -> None:
    cmp_, why = compare(EPS, "co_nvda", [snap(0.80, DISCLOSED + timedelta(minutes=1))], DISCLOSED, ASOF)
    assert cmp_ is None and why == "no_pre_event_consensus"


def test_pre_event_consensus_compared() -> None:
    cmp_, why = compare(
        EPS,
        "co_nvda",
        [
            snap(0.70, DISCLOSED - timedelta(days=3), exp_id="old"),
            snap(0.75, DISCLOSED - timedelta(hours=2), exp_id="new"),
        ],
        DISCLOSED,
        ASOF,
    )
    assert why is None and cmp_["consensus_exp_id"] == "new" and cmp_["consensus_value"] == 0.75  # type: ignore[index]
    assert cmp_["difference"] == pytest.approx(0.06) and cmp_["difference_pct"] == pytest.approx(8.0)  # type: ignore[index]
    assert cmp_["comparison_basis"] == "non_gaap"  # type: ignore[index]


def test_day_precision_must_be_earlier_date() -> None:
    same_day = datetime(2026, 11, 19, 5, 0, tzinfo=UTC)  # 00:00 ET same date, precision day
    assert compare(EPS, "co_nvda", [snap(0.75, same_day, precision="day")], DISCLOSED, ASOF)[0] is None
    prev_day = datetime(2026, 11, 18, 5, 0, tzinfo=UTC)
    assert compare(EPS, "co_nvda", [snap(0.75, prev_day, precision="day")], DISCLOSED, ASOF)[0] is not None


def test_snapshot_not_yet_available_is_ignored() -> None:
    s = snap(0.75, DISCLOSED - timedelta(hours=2), available=ASOF + timedelta(minutes=1))
    assert compare(EPS, "co_nvda", [s], DISCLOSED, ASOF) == (None, "no_pre_event_consensus")


def test_basis_mismatch() -> None:
    s = snap(0.75, DISCLOSED - timedelta(hours=2), metric="eps_non_gaap", basis="gaap")
    assert compare(EPS, "co_nvda", [s], DISCLOSED, ASOF) == (None, "no_same_basis_consensus")


def test_pct_metric_uses_pp() -> None:
    gm = check_facts(
        (fact("gross margin", 74.6, "pct", "GAAP gross margin was 74.6%", "gaap"),), "FY2027Q3"
    ).accepted[0]
    s = snap(73.5, DISCLOSED - timedelta(hours=2), metric="gross_margin_pct", basis="gaap") | {"unit": "pct"}
    cmp_, _ = compare(gm, "co_nvda", [s], DISCLOSED, ASOF)
    assert cmp_["difference_pp"] == pytest.approx(1.1) and "difference_pct" not in cmp_  # type: ignore[index,operator]


def test_snapshots_must_match_contract() -> None:
    with pytest.raises(pydantic.ValidationError):
        compare(EPS, "co_nvda", [snap(0.75, DISCLOSED) | {"expectation_type": "rumour"}], DISCLOSED, ASOF)


# ---------------------------------------------------------------- extract-0.3 behaviour
def seg_fact(metric: str, value: float, unit: str, quote: str, segment: str | None = None) -> ExtractedFact:
    return ExtractedFact(
        metric,
        value,
        unit,
        None,
        "FY2026Q3",
        None,
        quote,
        {"char_start": 0, "char_end": len(quote)},
        metric_label=metric,
        segment=segment,
    )


def test_table_row_scale_in_header() -> None:
    rep = check_facts(
        (seg_fact("net_income", 2428, "USD_million", "Net income ($M) $2,428 $1,243 Up 95%"),), None
    )
    assert rep.accepted and rep.accepted[0].value == pytest.approx(2.428e9)
    rep2 = check_facts(
        (seg_fact("revenue", 35166, "USD_million", "Net revenue $ 13,377 $ 11,536 $ 35,166"),), None
    )
    assert rep2.rejected[0]["reason"] == "value_not_in_quote"  # no scale anywhere -> still rejected


def test_segment_figures_do_not_conflict_with_company_total() -> None:
    rep = check_facts(
        (
            seg_fact("revenue", 13.4, "USD_billion", "revenue grew 45% to a record $13.4 billion"),
            seg_fact(
                "revenue",
                5.1,
                "USD_billion",
                "Data Center segment revenue was $5.1 billion",
                segment="Data Center",
            ),
        ),
        None,
    )
    assert len(rep.accepted) == 2 and {f.segment for f in rep.accepted} == {None, "Data Center"}


def test_other_metric_is_kept_out() -> None:
    rep = check_facts((seg_fact("other", 3.0, "USD_billion", "backlog was $3.0 billion"),), None)
    assert rep.accepted == [] and rep.rejected[0]["reason"] == "unknown_metric"


def test_schema_enums_follow_config() -> None:
    from sr.config import load
    from sr.llm.base import FACTS_SCHEMA

    item = FACTS_SCHEMA["properties"]["facts"]["items"]
    assert item["properties"]["metric"]["enum"] == [*load("earnings")["metrics"], "other"]
    assert item["properties"]["unit"]["enum"] == list(load("earnings")["units"])
    assert {"segment", "metric_label"} <= set(item["required"])


def test_growth_rates_may_exceed_100pct() -> None:
    rep = check_facts(
        (
            seg_fact("revenue_growth_yoy_pct", 221, "pct", "grew 221% year-over-year"),
            seg_fact("gross_margin_pct", 174.6, "pct", "gross margin was 174.6%"),
        ),
        None,
    )
    assert [f.metric for f in rep.accepted] == ["revenue_growth_yoy_pct"]
    assert rep.rejected[0]["reason"] == "pct_out_of_range"


# --- earnings-0.2 (OQ-39): document header scales, signed losses, compact scales. SYNTHETIC document. ---
DOC = (
    "Synthetic Corp (synthetic) condensed statement\n"
    "(In millions, except per share data)\n"
    "Revenue $ 7,436 $ 6,819\n"
    "Operating expenses 3,296 1,738\n" + "filler " * 200 + "\nShare data (in thousands)\n"
    "Weighted shares 2,431 2,410\n"
)


def doc_fact(metric: str, value: float, unit: str, quote: str) -> ExtractedFact:
    i = DOC.index(quote)
    return ExtractedFact(
        metric, value, unit, None, None, None, quote, {"char_start": i, "char_end": i + len(quote)}
    )


def test_table_row_scale_comes_from_the_header_above_it() -> None:
    f = doc_fact("operating_expenses", 3296, "USD_million", "Operating expenses 3,296 1,738")
    assert check_facts((f,), None).rejected[0]["reason"] == "value_not_in_quote"  # no document: strict
    rep = check_facts((f,), None, DOC)
    assert rep.accepted[0].value == 3296e6 and rep.rejected == []


def test_header_scale_must_match_the_unit() -> None:
    wrong = doc_fact("revenue", 7436, "USD_billion", "Revenue $ 7,436 $ 6,819")
    assert check_facts((wrong,), None, DOC).rejected[0]["reason"] == "value_not_in_quote"
    # the nearest header wins: "in thousands" sits between "in millions" and this row
    shares = doc_fact("revenue", 2431, "USD_million", "Weighted shares 2,431 2,410")
    assert check_facts((shares,), None, DOC).rejected[0]["reason"] == "value_not_in_quote"


def test_header_beyond_lookback_does_not_count() -> None:
    far = "(in millions)\n" + "x" * 9000 + "\nRevenue $ 7,436\n"
    f = ExtractedFact("revenue", 7436, "USD_million", None, None, None, "Revenue $ 7,436", {})
    assert check_facts((f,), None, far).rejected[0]["reason"] == "value_not_in_quote"


def test_losses_and_declines_may_be_signed() -> None:
    rep = check_facts(
        (
            seg_fact("operating_income", -134, "USD_million", "operating loss was $134 million"),
            seg_fact("revenue_growth_yoy_pct", -8, "pct", "revenue was $3.7 billion, down 8% year-over-year"),
        ),
        None,
    )
    assert [f.value for f in rep.accepted] == [-134e6, -8] and rep.rejected == []


def test_sign_flip_needs_a_cue_and_a_signed_metric() -> None:
    rep = check_facts(
        (
            seg_fact("operating_income", -134, "USD_million", "operating income was $134 million"),  # no cue
            seg_fact("revenue", -3.7, "USD_billion", "revenue was $3.7 billion, down 8%"),  # revenue >= 0
        ),
        None,
    )
    assert rep.accepted == [] and [r["reason"] for r in rep.rejected] == ["value_not_in_quote"] * 2


def test_compact_scale_suffix() -> None:
    rep = check_facts((seg_fact("revenue", 0.8, "USD_billion", "Gaming $0.8B"),), None)
    assert rep.accepted[0].value == 0.8e9
    rep2 = check_facts((seg_fact("revenue", 0.8, "USD", "Gaming $0.8B"),), None)  # $0.8B is not $0.80
    assert rep2.accepted == []


def test_foreign_currency_is_not_usd() -> None:
    nt = ExtractedFact(
        "revenue",
        1134.10,
        "USD_billion",
        "TWD",
        "Q1 2026",
        None,
        "First quarter consolidated revenue was NT$1,134.10 billion",
        {},
    )
    assert check_facts((nt,), None).rejected[0]["reason"] == "currency_not_supported:TWD"
    mislabelled = seg_fact("eps_gaap", 14.45, "USD_per_share", "diluted EPS of NT$14.45 per share")
    mislabelled = ExtractedFact(**{**mislabelled.__dict__, "basis": "gaap"})
    assert check_facts((mislabelled,), None).rejected[0]["reason"] == "value_not_in_quote"
    adr = ExtractedFact(
        "eps",
        2.32,
        "USD_per_share",
        "USD",
        "Q1 2026",
        "gaap",
        "diluted EPS of NT$14.45, or US$2.32 per ADR unit",
        {},
    )
    assert check_facts((adr,), None).accepted[0].value == 2.32
    twd_table = "(In Millions of New Taiwan Dollars)\nNet Revenue 514,806 467,580\n"
    row = ExtractedFact("revenue", 514806, "USD_million", None, None, None, "Net Revenue 514,806 467,580", {})
    assert check_facts((row,), None, twd_table).rejected[0]["reason"] == "value_not_in_quote"
