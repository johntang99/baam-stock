"""DP 1.24 valuation background (AC-42; OQ-54): explanation only, never a model feature. SYNTHETIC values."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from sr.events.valuation import (
    ExplanationOnlyField,
    FrameValuationSource,
    NoValuationSource,
    check_feature_inputs,
    peers_for,
    valuation_context,
)

T = datetime(2026, 12, 2, 16, 30, tzinfo=UTC)
NVDA = "sec_nvda"
PEERS = ["sec_amd", "sec_avgo", "sec_mu", "sec_qcom"]


def values(days: int = 800, peers: list[str] = PEERS) -> pd.DataFrame:
    """Daily forward P/E (synthetic): NVDA rises from 20 to 40, so today is its 3-year high; peers 18, 22, 26, 30."""
    rows = []
    for i in range(days):
        d = T - timedelta(days=days - 1 - i)
        rows.append(
            {
                "security_id": NVDA,
                "as_of": d,
                "fwd_pe": 20 + 20 * i / (days - 1),
                "ev_sales_ntm": 15.0,
                "available_at": d + timedelta(hours=1),
            }
        )
        for k, p in enumerate(peers):
            rows.append(
                {
                    "security_id": p,
                    "as_of": d,
                    "fwd_pe": 18.0 + 4 * k,
                    "ev_sales_ntm": None,
                    "available_at": d + timedelta(hours=1),
                }
            )
    return pd.DataFrame(rows)


def test_context_fields_are_complete() -> None:
    c = valuation_context(FrameValuationSource(values()), NVDA, PEERS, T + timedelta(hours=2))
    assert c is not None
    assert set(c) == {
        "as_of",
        "fwd_pe",
        "fwd_pe_pctile_3y",
        "peer_median_fwd_pe",
        "ev_sales_ntm",
        "source_id",
        "note",
    }
    assert c["fwd_pe"] == 40.0 and c["fwd_pe_pctile_3y"] == 100.0  # today is the 3-year high
    assert c["peer_median_fwd_pe"] == 24.0  # median of 18, 22, 26, 30
    assert c["as_of"].startswith("2026-12-02") and c["source_id"] == "src_valuation_synthetic"
    assert "近 3 年 100 分位" in c["note"] and "不进入短线模型" in c["note"]


def test_point_in_time() -> None:
    v = values()
    spike = pd.DataFrame(
        [
            {
                "security_id": NVDA,
                "as_of": T,
                "fwd_pe": 999.0,
                "ev_sales_ntm": None,
                "available_at": T + timedelta(days=1),
            }
        ]
    )
    c = valuation_context(
        FrameValuationSource(pd.concat([v, spike], ignore_index=True)), NVDA, PEERS, T + timedelta(hours=2)
    )
    assert c is not None and c["fwd_pe"] == 40.0  # a value published after the analysis time is not seen
    earlier = valuation_context(FrameValuationSource(v), NVDA, PEERS, T - timedelta(days=400))
    assert earlier is not None and earlier["fwd_pe"] < 40.0


def test_thin_data_gives_nulls_not_guesses() -> None:
    c = valuation_context(
        FrameValuationSource(values(days=30, peers=PEERS[:2])), NVDA, PEERS, T + timedelta(hours=2)
    )
    assert c is not None and c["fwd_pe_pctile_3y"] is None and c["peer_median_fwd_pe"] is None


def test_no_licensed_source_no_context() -> None:
    assert valuation_context(NoValuationSource(), NVDA, PEERS, T) is None
    assert (
        valuation_context(
            FrameValuationSource(values(peers=[])[lambda d: d.security_id != NVDA]), NVDA, PEERS, T
        )
        is None
    )


# ---------------------------------------------------------------- AC-42: never a model feature
def test_feature_building_refuses_valuation_fields() -> None:
    from sr.train.train import design

    for bad in (
        ["fwd_pe"],
        ["f_fwd_pe_pctile_3y"],
        ["market_explanation.valuation_context"],
        ["qqq_ret_30m", "peer_median_fwd_pe"],
    ):
        with pytest.raises(ExplanationOnlyField):
            check_feature_inputs(bad)
    check_feature_inputs(["qqq_ret_30m", "rv_30m"])  # ordinary features are fine
    frame = pd.DataFrame({"f_fwd_pe": [30.0], "f_qqq_ret_30m": [0.1]})
    with pytest.raises(ExplanationOnlyField):
        design(frame, ["qqq_ret_30m", "fwd_pe"])


def test_publish_time_feature_row_refuses_valuation_columns(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import sr.forecast.features as ff
    from tests.test_forecast import DAY, SLOT, history

    real = ff.features_at
    monkeypatch.setattr(ff, "features_at", lambda *a, **k: {**real(*a, **k), "fwd_pe": 30.0})
    with pytest.raises(ExplanationOnlyField):
        ff.feature_row({}, NVDA, ["sec_amd"], SLOT, DAY, 0.6, history())


def test_event_feature_inputs_refuse_valuation(conn) -> None:  # type: ignore[no-untyped-def]
    from sr.features.llm_gate import event_feature_inputs

    with pytest.raises(ExplanationOnlyField):
        event_feature_inputs(conn, "eav_any", fields=("facts", "market_explanation.valuation_context"))


# ---------------------------------------------------------------- DB: peers and the explanation
def test_peers_fall_back_to_the_basket(conn) -> None:  # type: ignore[no-untyped-def]
    got = peers_for(conn, NVDA, T)
    assert len(got) == 11 and NVDA not in got and "sec_amd" in got  # seeds have no valuation_peers yet
    conn.execute(
        "update company_profile_versions set valuation_peers = '{AMD,AVGO}' where company_id = 'co_nvda'"
    )
    assert peers_for(conn, NVDA, T) == ["sec_amd", "sec_avgo"]


def _event_with_v1(conn, doc_storage) -> str:  # type: ignore[no-untyped-def]
    from sr.events.merge import EvidenceIn, attach_evidence
    from sr.events.versions import publish_analysis
    from sr.evidence.collection_log import run_collection
    from tests.test_collection_reasoning import ASOF, WINDOW, scenario

    sources, _ = scenario(conn)
    res = run_collection(conn, NVDA, sources, WINDOW, ASOF, storage=doc_storage, now=ASOF)
    item = conn.execute(
        "select * from collection_items where collection_run_id = %s and disposition = 'kept' and channel = 'news_wire' limit 1",
        (res.collection_run_id,),
    ).fetchone()
    m = attach_evidence(
        conn,
        "policy:BIS:val",
        "policy_export",
        EvidenceIn(item["doc_version_id"], "rule (synthetic)", {}, "primary_confirmed", "o"),
        now=ASOF,
    )
    v1 = datetime(2026, 12, 2, 16, 1, tzinfo=UTC)
    publish_analysis(
        conn,
        m.event_id,
        NVDA,
        v1,
        lambda s: {
            "analysis_kind": "flash",
            "prediction_readiness": {"event_outcome": {"status": "manual_review", "reason": "x"}},
            "market_explanation": {
                "status": "insufficient",
                "observed_facts": [],
                "possible_drivers": [],
                "counter_evidence": [],
                "unexplained": [],
                "concurrent_events": [],
            },
        },
        v1,
    )
    return m.event_id


def _quotes(asof):  # type: ignore[no-untyped-def]
    from tests.test_reaction_explain import make_quotes, ramp, visible

    peers = {
        p: ramp(100, 100, datetime(2026, 12, 2, 15, tzinfo=UTC), datetime(2026, 12, 2, 15, 1, tzinfo=UTC))
        for p in ["sec_amd", "sec_avgo", "sec_mu"]
    }
    q = make_quotes(
        {
            NVDA: ramp(
                100, 99, datetime(2026, 12, 2, 15, 45, tzinfo=UTC), datetime(2026, 12, 2, 16, 20, tzinfo=UTC)
            ),
            **peers,
        },
        datetime(2026, 12, 2, 15, 0, tzinfo=UTC),
        asof,
    )
    return visible(q, asof)


@pytest.mark.parametrize("with_source", [True, False])
def test_explanation_carries_valuation_only_with_a_source(conn, doc_storage, with_source: bool) -> None:  # type: ignore[no-untyped-def]
    from sr.events.explain import publish_explanation

    eid = _event_with_v1(conn, doc_storage)
    asof = datetime(2026, 12, 2, 16, 30, tzinfo=UTC)
    src = FrameValuationSource(values()) if with_source else NoValuationSource()
    ctx = valuation_context(src, NVDA, PEERS, asof)
    w = {p: 1 / 3 for p in ["sec_amd", "sec_avgo", "sec_mu"]}
    out = publish_explanation(conn, eid, NVDA, asof, asof, _quotes(asof), weights=w, valuation=ctx)
    ex = conn.execute(
        "select market_explanation from event_analysis_versions where analysis_id = %s",
        (out.publish.analysis_id,),
    ).fetchone()["market_explanation"]
    if with_source:
        v = ex["valuation_context"]  # AC-42: fields present and as_of shown
        assert set(v) >= {"as_of", "fwd_pe", "fwd_pe_pctile_3y", "peer_median_fwd_pe", "source_id", "note"}
        # today's value is only available at 17:30, so a 16:30 analysis shows yesterday's (point in time)
        assert v["as_of"].startswith("2026-12-01") and v["fwd_pe"] < 40.0
    else:
        assert "valuation_context" not in ex  # no source: no row
    assert np.isfinite(len(ex["observed_facts"]))
