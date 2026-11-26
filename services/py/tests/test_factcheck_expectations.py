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
