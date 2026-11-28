"""DP 1.23 run state, source issues, display_state and snapshot validity (AC-49 Phase 1 part; D-41; OQ-53). SYNTHETIC."""

import json
from datetime import timedelta

import pytest

from sr.settle.settle import settle
from sr.snapshot.builder import Trigger, build_snapshot
from sr.snapshot.quality import assess, source_issues
from tests.test_settle import DUE, P, make_prediction, quotes, setup_models
from tests.test_snapshot_builder import NVDA, collection_run, day_quotes, et


# ---------------------------------------------------------------- quality rules (no DB)
def test_source_issues() -> None:
    run = {
        "sources_polled": [
            {"source_id": "src_a", "status": "ok", "latency_ms": 800},
            {"source_id": "src_b", "status": "timeout", "latency_ms": 30000},
            {"source_id": "src_c", "status": "ok", "latency_ms": 540000},
        ]
    }
    assert source_issues(run) == [
        {"source_id": "src_b", "issue": "timeout"},
        {"source_id": "src_c", "issue": "latency", "lag_s": 540},
    ]
    assert source_issues(None) == []


def test_assess_priorities() -> None:
    t = et(10, 20)
    base = dict(regular=True, session_open_at=et(9, 30), as_of=t, day_return_pct=0.5, relative_pp=0.2)
    assert assess(**base, market_watermark=t - timedelta(seconds=1), issues=[])[:2] == ("ok", "complete")
    assert assess(**base, market_watermark=t - timedelta(minutes=5), issues=[])[:2] == ("stale", "degraded")
    assert assess(**base, market_watermark=et(9, 0), issues=[])[:2] == ("failed", "failed")
    late = [{"source_id": "src_c", "issue": "latency", "lag_s": 540}]
    q, rs, issues = assess(**base, market_watermark=t - timedelta(seconds=1), issues=late)
    assert (q, rs) == ("partial", "degraded") and issues == late  # results, but a source was late
    outside = dict(base, regular=False, relative_pp=None)
    assert (
        assess(**outside, market_watermark=et(9, 0), issues=[])[0] == "ok"
    )  # no market rules outside regular hours


# ---------------------------------------------------------------- snapshots (DB)
def test_late_or_failed_source_degrades_the_snapshot(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(10, 18))
    conn.execute(
        "update collection_runs set sources_polled = %s",
        (
            json.dumps(
                [
                    {"source_id": "src_news_a", "status": "ok", "latency_ms": 540000},
                    {"source_id": "src_fr", "status": "timeout", "latency_ms": 30000},
                ]
            ),
        ),
    )
    as_of = et(10, 20)
    q, closes = day_quotes(conn, as_of)
    row = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", as_of), q, closes, as_of).row
    assert row["data_quality"] == "partial" and row["run_state"] == "degraded"
    assert {"source_id": "src_news_a", "issue": "latency", "lag_s": 540} in row[
        "quality_issues"
    ]  # DC example shape
    assert {"source_id": "src_fr", "issue": "timeout"} in row["quality_issues"]


def test_ac49_last_valid_points_to_the_latest_ok(conn) -> None:  # type: ignore[no-untyped-def]
    collection_run(conn, et(10, 18))
    ok_at = et(10, 20)
    q, closes = day_quotes(conn, ok_at)
    first = build_snapshot(conn, NVDA, Trigger("scheduled", "sched_5m", ok_at), q, closes, ok_at).row
    assert (
        first["data_quality"] == "ok"
        and first["run_state"] == "complete"
        and first["valid_until"] == et(10, 30)
    )
    collection_run(conn, et(10, 24))  # new evidence, but quotes stopped
    bad = build_snapshot(
        conn, NVDA, Trigger("scheduled", "sched_5m", et(10, 25)), q.iloc[0:0], closes, et(10, 25)
    ).row
    assert bad["data_quality"] != "ok" and bad["last_valid_at"] == ok_at
    cur = conn.execute(
        "select * from security_snapshot_current_at(%s) where security_id = 'sec_nvda'", (et(10, 26),)
    ).fetchone()
    assert (
        cur["snapshot_id"] == bad["snapshot_id"] and cur["last_valid_at"] == ok_at and cur["expired"] is False
    )
    later = conn.execute(
        "select * from security_snapshot_current_at(%s) where security_id = 'sec_nvda'", (et(10, 40),)
    ).fetchone()
    assert later["expired"] is True  # past valid_until (10:35): shown as 已过期
    then = conn.execute(
        "select * from security_snapshot_current_at(%s) where security_id = 'sec_nvda'", (et(10, 22),)
    ).fetchone()
    assert then["snapshot_id"] == first["snapshot_id"]  # point in time: the later snapshot did not exist yet


# ---------------------------------------------------------------- display_state (DB)
def state(conn, pid: str, at) -> tuple[str, str | None]:  # type: ignore[no-untyped-def]
    r = conn.execute(
        "select display_state, superseded_by from prediction_display_state_at(%s) where prediction_id = %s",
        (at, pid),
    ).fetchone()
    return (r["display_state"], r["superseded_by"]) if r else ("absent", None)


def test_ac49_display_states(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    a = make_prediction(conn, 1)
    assert state(conn, a, P - timedelta(seconds=1)) == ("absent", None)  # not published yet
    assert state(conn, a, P + timedelta(minutes=5)) == ("current", None)
    assert state(conn, a, P + timedelta(hours=2)) == ("expired", None)  # past valid_until, not settled
    # a revision published at P + 10 min supersedes it from then on
    b = "pred_rev"
    conn.execute(
        """insert into prediction_runs (run_id, trigger_type, snapshot_id, feature_snapshot_id, model_version_id, calibration_version,
               baseline_model_version_id, publish_deadline, published_at, idempotency_key)
           values ('run_rev', 'event', 'snap_t', 'f', 'mdl_t', 'c', 'mdl_b', %s, %s, 'run_rev')""",
        (P + timedelta(minutes=10), P + timedelta(minutes=10)),
    )
    conn.execute(
        """insert into predictions (prediction_id, run_id, target_row_id, security_id, status, probabilities, predicted_class,
               sigma_hat_pp, threshold_pp, display_tier, is_primary, sampling_rule, supersedes_prediction_id, valid_until,
               locked, published_at)
           select %s, 'run_rev', target_row_id, security_id, 'published', probabilities, predicted_class, sigma_hat_pp,
                  threshold_pp, display_tier, false, 'revision', prediction_id, valid_until, locked, %s
             from predictions where prediction_id = %s""",
        (b, P + timedelta(minutes=10), a),
    )
    assert state(conn, a, P + timedelta(minutes=5)) == ("current", None)
    assert state(conn, a, P + timedelta(minutes=15)) == ("superseded", b)
    # once settled it shows as settled (the newer version is still linked)
    settle(conn, a, quotes(conn, 1.0, 0.5), DUE)
    assert state(conn, a, DUE) == ("settled", b)
    # the now() view is the function at now() (these synthetic rows are dated after today's clock, so neither has them)
    view = conn.execute(
        "select prediction_id, display_state from prediction_display_state order by 1"
    ).fetchall()
    fn = conn.execute(
        "select prediction_id, display_state from prediction_display_state_at(now()) order by 1"
    ).fetchall()
    assert view == fn


def test_abstained_prediction_expires(conn) -> None:  # type: ignore[no-untyped-def]
    setup_models(conn)
    pid = make_prediction(conn, 1, status="abstained")
    assert state(conn, pid, P + timedelta(minutes=1)) == ("current", None)
    assert state(conn, pid, P + timedelta(hours=2)) == ("expired", None)


@pytest.mark.parametrize("view", ["prediction_display_state", "security_snapshot_current"])
def test_views_respect_rls(conn, view: str) -> None:  # type: ignore[no-untyped-def]
    r = conn.execute("select reloptions from pg_class where relname = %s", (view,)).fetchone()
    assert "security_invoker=true" in (r["reloptions"] or [])
