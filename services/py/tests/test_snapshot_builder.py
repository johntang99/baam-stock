"""DP 1.10 security snapshots + same-watermark merge (AC-11, AC-12, AC-40; D-17, D-28, D-41; OQ-44). SYNTHETIC."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import pytest

from sr.calendar import get_calendar
from sr.events.versions import publish_analysis
from sr.marketdata.providers.fixture import FixtureProvider
from sr.snapshot.builder import Trigger, build_snapshot, market_state, replay_session, schedule, valid_until
from sr.timeguard import LookaheadError
from tests.test_reaction_explain import make_quotes, ramp, visible

CAL = get_calendar()
D = date(2026, 12, 2)  # Wednesday, EST: 09:30 ET = 14:30Z
OPEN = datetime(2026, 12, 2, 14, 30, tzinfo=UTC)
NVDA = "sec_nvda"


def et(h: int, m: int, d: date = D) -> datetime:
    from datetime import time

    from sr.calendar.calendar import et_to_utc

    return et_to_utc(d, time(h, m))


# ---------------------------------------------------------------- schedule and validity (no DB)
def test_schedule_every_5_minutes_plus_session_checks() -> None:
    t = schedule(CAL.session(D))
    sched = [x for x in t if x.trigger_type == "scheduled"]
    checks = [x for x in t if x.trigger_type == "session_check"]
    assert len(sched) == 78 and sched[0].analysis_as_of == OPEN and sched[-1].analysis_as_of == et(15, 55)
    assert [c.analysis_as_of for c in checks] == [et(9, 35), et(15, 45)]
    # half day (2026-11-27, close 13:00 ET): 15:45 falls outside the session
    half = schedule(CAL.session(date(2026, 11, 27)))
    assert [c.trigger_ref for c in half if c.trigger_type == "session_check"] == ["check_0935"]
    assert max(x.analysis_as_of for x in half) == et(12, 55, date(2026, 11, 27))
    assert schedule(CAL.session(date(2026, 11, 26))) == []  # Thanksgiving: closed


def test_valid_until_d41() -> None:
    s = CAL.session(D)
    assert valid_until(et(10, 20), s) == et(10, 30)  # next scheduled 10:25 + 5 min
    assert valid_until(et(10, 21), s) == et(10, 30)
    assert valid_until(et(15, 57), s) == et(9, 30, date(2026, 12, 3))  # no more grid times today
    assert valid_until(et(8, 0), s) == et(9, 30)  # pre-market: today's open
    fri = date(2026, 12, 4)
    assert valid_until(et(16, 30, fri), CAL.session(fri)) == et(9, 30, date(2026, 12, 7))  # over the weekend


def test_market_state() -> None:
    s = CAL.session(D)
    assert market_state(et(8, 0), s, None) == "pre_market"
    assert market_state(et(10, 0), s, None) == "regular"
    assert market_state(et(16, 0), s, None) == "post_market"
    assert market_state(et(10, 0), s, {"halted": True}) == "halted"
    assert market_state(et(10, 0), CAL.session(date(2026, 12, 5)), None) == "closed"  # Saturday


# ---------------------------------------------------------------- DB helpers


def peers(conn) -> list[str]:  # type: ignore[no-untyped-def]
    row = conn.execute(
        "select constituents from benchmark_versions where benchmark_id = 'bm_semis_peer_ex_nvda'"
    ).fetchone()
    return [c["security_id"] for c in row["constituents"]]


def collection_run(conn, window_to: datetime, failed: int = 0) -> None:  # type: ignore[no-untyped-def]
    import json

    conn.execute(
        """insert into collection_runs (collection_run_id, security_id, window_from, window_to, counts, started_at)
           values (%s, 'sec_nvda', %s, %s, %s, %s)""",
        (
            f"cr_{window_to:%H%M%S}",
            window_to - timedelta(hours=1),
            window_to,
            json.dumps({"failed": failed}),
            window_to,
        ),
    )


def day_quotes(
    conn, as_of: datetime, stock_ret: float = 1.0, peer_ret: float = 0.5, peers_up: int | None = None
):  # type: ignore[no-untyped-def]
    ps = peers(conn)
    live = ps if peers_up is None else ps[:peers_up]
    paths = {NVDA: ramp(100, 100 * (1 + stock_ret / 100), OPEN, as_of - timedelta(minutes=1))}
    paths |= {p: ramp(50, 50 * (1 + peer_ret / 100), OPEN, as_of - timedelta(minutes=1)) for p in live}
    q = visible(make_quotes(paths, as_of - timedelta(minutes=25), as_of), as_of)
    closes: dict[str, float | None] = {NVDA: 100.0, **{p: 50.0 for p in ps}}
    return q[q["ts"] >= pd.Timestamp(as_of - timedelta(seconds=60))].reset_index(drop=True), closes


# ---------------------------------------------------------------- snapshot content
def test_no_news_snapshot(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(10, 18))
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of, stock_ret=0.61, peer_ret=0.39)
    r = build_snapshot(
        conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q, closes, as_of + timedelta(milliseconds=600)
    )
    row = r.row
    assert r.status == "published" and row["snapshot_id"].startswith("snap_")
    assert row["event_analysis_ids"] == [] and row["new_catalyst_found"] is False  # AC-11
    assert row["day_return_pct"] == pytest.approx(0.61, abs=1e-6)
    assert row["day_relative_pp"] == pytest.approx(0.22, abs=1e-6)  # the DC §8.1 example numbers
    assert row["explanation_status"] == "partial"
    assert (
        row["explanation_summary"].startswith("监测来源范围内暂未发现新催化剂")
        and "+0.22pp" in row["explanation_summary"]
    )
    assert row["data_quality"] == "ok" and row["run_state"] == "complete" and row["last_valid_at"] == as_of
    assert row["market_state"] == "regular" and row["session_date"] == D
    assert row["evidence_watermark"] == et(10, 18)  # no items: the collection run's window_to
    assert row["market_watermark"] <= as_of and row["valid_until"] == et(10, 30)
    assert row["benchmark_version_id"] == "bmv_semis_peer_ex_nvda_v1"
    assert row["prediction_readiness"]["stock_reaction"] == {
        "status": "ready",
        "reason": "market_inputs_valid",
        "allowed_models": ["market_baseline"],
    }
    stored = conn.execute(
        "select * from reference_quotes where quote_id = %s", (row["last_quote_id"],)
    ).fetchone()
    assert stored is not None and stored["security_id"] == NVDA


def test_same_watermark_merge(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(10, 18))
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of)
    a = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q, closes, as_of)
    b = build_snapshot(conn, NVDA, Trigger("session_check", "check_1020", as_of), q, closes, as_of)
    c = build_snapshot(
        conn, NVDA, Trigger("on_demand", "req_1", as_of + timedelta(milliseconds=400)), q, closes, as_of
    )
    assert (a.status, b.status, c.status) == (
        "published",
        "merged",
        "merged",
    )  # inputs unchanged -> one snapshot
    assert a.snapshot_id == b.snapshot_id == c.snapshot_id
    assert conn.execute("select count(*) as n from security_state_snapshots").fetchone()["n"] == 1
    # a newer quote moves the market watermark -> a new snapshot
    later = as_of + timedelta(seconds=5)
    q2, _ = day_quotes(conn, later)
    assert (
        build_snapshot(conn, NVDA, Trigger("on_demand", "req_2", later), q2, closes, later).status
        == "published"
    )


def test_ac40_basket_unavailable(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(10, 18))
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of, peers_up=9)  # 2 of 11 constituents have no quotes (> 1 missing)
    row = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q, closes, as_of).row
    assert row["day_return_pct"] == pytest.approx(1.0, abs=1e-6) and row["day_relative_pp"] is None
    assert row["data_quality"] == "partial" and row["run_state"] == "degraded"
    assert {"issue": "benchmark_unavailable"} in row["quality_issues"]
    assert "基准不可计算" in row["explanation_summary"]
    assert row["prediction_readiness"]["stock_reaction"]["status"] == "missing_inputs"


def test_stale_and_failed_quality(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(10, 18))
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of)
    first = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q, closes, as_of)
    assert first.row["data_quality"] == "ok"
    empty = q.iloc[0:0]
    # 5 minutes later, no new quote and no new evidence: both watermarks are unchanged, so the trigger merges into
    # the 10:20 snapshot (DC dedupe key); it expires at its valid_until (10:30, D-41) instead
    later = et(10, 25)
    same = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", later), empty, closes, later)
    assert same.status == "merged" and same.snapshot_id == first.snapshot_id
    # new evidence arrives but quotes have stopped: a new snapshot, stale, last valid time kept
    collection_run(conn, et(10, 24))
    row = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", later), empty, closes, later).row
    assert row["data_quality"] == "stale" and row["run_state"] == "degraded"
    assert row["market_watermark"] == first.row["market_watermark"] and row["last_valid_at"] == as_of
    assert row["quality_issues"][-1]["issue"] == "stale_quotes" and row["quality_issues"][-1]["lag_s"] > 60


def test_no_quote_in_the_session_is_failed(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(10, 18))
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of)
    row = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q.iloc[0:0], closes, as_of).row
    assert row["data_quality"] == "failed" and row["run_state"] == "failed" and row["last_valid_at"] is None
    assert row["day_return_pct"] is None and row["explanation_status"] == "insufficient"


def test_no_collection_run_is_flagged(conn) -> None:  # type: ignore[no-untyped-def]
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of)
    row = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q, closes, as_of).row
    assert {"issue": "no_collection_run"} in row["quality_issues"] and row["data_quality"] == "partial"
    assert row["evidence_watermark"] == et(0, 0)  # 00:00 ET of the session date


def test_post_market_has_no_regular_prediction(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(16, 10))
    as_of = et(16, 20)
    q, closes = day_quotes(conn, as_of)
    row = build_snapshot(conn, NVDA, Trigger("market_move", "move_rule", as_of), q, closes, as_of).row
    assert row["market_state"] == "post_market"
    assert row["prediction_readiness"]["stock_reaction"] == {
        "status": "not_applicable",
        "reason": "outside_regular_session",
    }
    assert row["valid_until"] == et(9, 30, date(2026, 12, 3))  # D-41: the next session's first snapshot


def test_quotes_after_as_of_raise(conn) -> None:  # type: ignore[no-untyped-def]
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of + timedelta(seconds=30))
    with pytest.raises(LookaheadError):
        build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q, closes, as_of)


# ---------------------------------------------------------------- AC-12 policy day
def test_ac12_policy_day_snapshot_includes_the_analysis(conn) -> None:  # type: ignore[no-untyped-def]
    from sr.events.readiness import stock_reaction

    ev = conn.execute(
        """insert into events (event_id, category, identity_key, progress_status, evidence_status, analysis_status,
                               row_version, first_seen_at)
           values ('evt_policy_demo', 'policy_export', 'policy:BIS:demo', 'effective', 'primary_confirmed', 'partial', 1, %s)
           returning event_id""",
        (et(9, 0),),
    ).fetchone()
    conn.execute(
        "insert into event_security_links (event_id, security_id, relation) values (%s, 'sec_nvda', 'regulated_party')",
        (ev["event_id"],),
    )
    payload: dict[str, Any] = {
        "analysis_kind": "flash",
        "market_explanation": {
            "status": "partial",
            "observed_facts": [],
            "possible_drivers": [],
            "counter_evidence": [],
            "unexplained": [],
            "concurrent_events": [],
        },
        "prediction_readiness": {
            "event_outcome": {"status": "manual_review", "reason": "outcome_question_not_defined"},
            "stock_reaction": stock_reaction("policy_export", market_inputs_ready=True),
        },
    }
    pub = publish_analysis(conn, ev["event_id"], NVDA, et(10, 5), lambda s: payload, et(10, 6))
    collection_run(conn, et(10, 18))
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of)
    row = build_snapshot(conn, NVDA, Trigger("event", ev["event_id"], as_of), q, closes, as_of).row
    assert row["event_analysis_ids"] == [pub.analysis_id] and row["new_catalyst_found"] is True
    assert row["prediction_readiness"]["stock_reaction"]["allowed_models"] == ["market_baseline"]  # AC-12
    assert row["explanation_status"] == "partial"
    # an analysis published after as_of is invisible (point in time)
    early = build_snapshot(
        conn, NVDA, Trigger("scheduled", "sched_5m", et(10, 5)), *day_quotes(conn, et(10, 5)), et(10, 5)
    ).row
    assert early["event_analysis_ids"] == []


# ---------------------------------------------------------------- AC-11 on the synthetic fixture
def test_ac11_no_news_day_every_5_minutes(conn, fixture_path) -> None:  # type: ignore[no-untyped-def]
    day = date(2026, 12, 1)
    collection_run(conn, datetime(2026, 12, 1, 14, 0, tzinfo=UTC))
    provider = FixtureProvider(fixture_path)
    first = provider.quotes_1s(
        ["sec_nvda", *peers(conn)],
        datetime(2026, 12, 1, 14, 30, tzinfo=UTC),
        datetime(2026, 12, 1, 14, 30, 5, tzinfo=UTC),
    )
    closes = (
        first.sort_values("ts")
        .groupby("security_id")
        .first()
        .pipe(lambda d: ((d["bid"] + d["ask"]) / 2).to_dict())
    )
    res = replay_session(conn, provider, NVDA, day, prev_close=closes)
    published = [r for r in res if r.status == "published"]
    assert len(res) == 80 and len(published) == 78  # the two session checks merge with the 5-minute snapshots
    times = sorted(r.row["analysis_as_of"] for r in published)
    assert all(b - a == timedelta(minutes=5) for a, b in zip(times, times[1:], strict=False))
    for r in published:
        assert r.row["event_analysis_ids"] == [] and r.row["new_catalyst_found"] is False
        assert r.row["market_watermark"] <= r.row["analysis_as_of"] < r.row["valid_until"]
    assert (
        sum(r.row["data_quality"] == "ok" for r in published) >= 70
    )  # the fixture has a few bad-quote stretches
