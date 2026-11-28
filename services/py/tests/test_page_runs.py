"""DP 2.07-2.08 database side: role policies and the page's request functions (DC §6, §10; AC-34, AC-35; OQ-63).

Calls run as the `authenticated` role with JWT claims set the way PostgREST sets them, so the policies and the
security-definer functions are exercised exactly as the web app reaches them. SYNTHETIC data.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from sr.jobs.handlers import LiveContext, make_handlers
from sr.jobs.worker import Worker
from sr.pipeline import orchestrator as orch
from tests.test_dataset import PEERS_ALL, REFS, FrameProvider, synthetic_quotes
from tests.test_forecast import NVDA, SLOT
from tests.test_pipeline import ctx

TARGETS = ["regular_60m", "regular_60m_move"]


@pytest.fixture(scope="module")
def provider() -> FrameProvider:
    return FrameProvider(synthetic_quotes([NVDA, *PEERS_ALL, *REFS], seed=21))


@contextmanager
def as_user(conn, sub: str | None, role: str | None) -> Iterator[None]:  # type: ignore[no-untyped-def]
    claims: dict = {} if sub is None else {"sub": sub}  # type: ignore[type-arg]
    if role:
        claims["app_metadata"] = {"app_role": role}
    with conn.transaction():
        conn.execute("set local role authenticated")
        conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
        yield


def request(conn, sub, role, mode="live", as_of=None, reuse="reuse_if_unchanged", targets=TARGETS):  # type: ignore[no-untyped-def]
    with as_user(conn, sub, role):
        r = conn.execute(
            "select * from request_pipeline_run(%s, %s, %s, %s, %s)", ([NVDA], targets, mode, as_of, reuse)
        ).fetchone()
    return r["pipeline_run_id"], r["created"]


def worker(conn, provider, tmp_path, now: datetime) -> Worker:  # type: ignore[no-untyped-def]
    c = ctx(conn, provider, tmp_path)
    lc = LiveContext(provider, c.prev_close or {}, lambda: now, run_context=lambda at, lag: c)
    return Worker(conn, make_handlers(lc), clock=lambda: now, worker_id="t")


# ---------------------------------------------------------------- policies (DC §10)
def test_no_role_sees_nothing_and_viewers_see_reference_data(conn) -> None:  # type: ignore[no-untyped-def]
    with as_user(conn, "u0", None):
        assert conn.execute("select count(*) as n from securities").fetchone()["n"] == 0
    with as_user(conn, "u1", "viewer"):
        assert conn.execute("select count(*) as n from securities").fetchone()["n"] == 18
        assert conn.execute("select count(*) as n from jobs").fetchone()["n"] == 0  # ops data: researcher+
    with as_user(conn, "u1", "researcher"):
        conn.execute("select count(*) from jobs")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), as_user(conn, "u1", "admin"):
        conn.execute("update securities set primary_exchange = 'XNYS' where security_id = 'sec_nvda'")


def test_viewer_rules_and_dedupe(conn) -> None:  # type: ignore[no-untyped-def]
    a, made = request(conn, "u1", "viewer")
    b, again = request(conn, "u1", "viewer", targets=list(reversed(TARGETS)))
    c, third = request(conn, "u1", "viewer")
    assert made and not again and not third and a == b == c  # AC-35: three clicks, one run
    d, _ = request(conn, "u2", "viewer")
    assert d != a  # another user's identical request is a separate run
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        request(conn, "u1", "viewer", mode="replay", as_of=SLOT)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        request(conn, "u1", "viewer", reuse="force_recompute")
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        request(conn, "u1", "researcher", mode="supplement")  # needs base_run_id: not through this function
    with as_user(conn, "u2", "viewer"):
        ids = [r["pipeline_run_id"] for r in conn.execute("select pipeline_run_id from pipeline_runs")]
    assert ids == [d]  # viewers see only their own runs
    job = conn.execute("select job_type, payload from jobs where pipeline_run_id = %s", (a,)).fetchone()
    assert job["job_type"] == "pipeline_step" and job["payload"] == {"pipeline_run_id": a}
    key = conn.execute(
        "select idempotency_key, as_of from pipeline_runs where pipeline_run_id = %s", (a,)
    ).fetchone()
    assert key["idempotency_key"] == orch.idempotency_key([NVDA], TARGETS, key["as_of"], "live", "u1")


# ---------------------------------------------------------------- AC-34 / AC-35 through the worker
def test_page_run_executes_and_reuses(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    rid, _ = request(conn, "r1", "researcher", mode="replay", as_of=SLOT)
    w = worker(conn, provider, tmp_path, SLOT + timedelta(seconds=1))
    (rec,) = w.drain()
    assert rec.status == "succeeded"
    run = conn.execute("select * from pipeline_runs where pipeline_run_id = %s", (rid,)).fetchone()
    assert run["status"] in ("succeeded", "partial") and run["requested_by"] == "r1"
    steps = conn.execute(
        "select step, status from pipeline_run_steps where pipeline_run_id = %s order by step_no", (rid,)
    )
    assert [s["step"] for s in steps] == list(orch.STEPS)  # all 8 steps written
    preds = conn.execute("select sampling_rule, is_primary, published_at from predictions").fetchall()
    assert len(preds) == 2 and {(p["sampling_rule"], p["is_primary"]) for p in preds} == {
        ("on_demand", False)
    }
    # same inputs from another researcher: a new run that reuses, nothing new published
    rid2, _ = request(conn, "r2", "researcher", mode="replay", as_of=SLOT)
    w.drain()
    out = conn.execute("select outputs from pipeline_runs where pipeline_run_id = %s", (rid2,)).fetchone()[
        "outputs"
    ]
    assert rid2 != rid and out["reused"] is True
    assert conn.execute("select count(*) as n from predictions").fetchone()["n"] == 2


def test_injected_failure_is_retried_and_resumes(conn, provider, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    real, calls = orch.forecast_snapshot, {"n": 0}

    def flaky(*a, **k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("model server unavailable (synthetic)")
        return real(*a, **k)

    monkeypatch.setattr(orch, "forecast_snapshot", flaky)
    rid, _ = request(conn, "r1", "researcher", mode="replay", as_of=SLOT)
    t = SLOT + timedelta(seconds=1)
    (first,) = worker(conn, provider, tmp_path, t).drain()
    assert first.status == "retry_wait"
    st = {
        s["step"]: s
        for s in conn.execute("select * from pipeline_run_steps where pipeline_run_id = %s", (rid,))
    }
    assert st["infer"]["status"] == "failed"  # the failed step is kept for the retry
    (second,) = worker(conn, provider, tmp_path, t + timedelta(seconds=31)).drain()  # after the 30 s backoff
    assert second.status == "succeeded"
    st = {
        s["step"]: s
        for s in conn.execute("select * from pipeline_run_steps where pipeline_run_id = %s", (rid,))
    }
    assert st["infer"]["attempt"] == 2 and st["build_snapshot"]["attempt"] == 1  # resumed, not redone


def test_cancel_before_and_during_a_run(conn, provider, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    rid, _ = request(conn, "u1", "viewer")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), as_user(conn, "u2", "viewer"):
        conn.execute("select cancel_pipeline_run(%s)", (rid,))  # not your run
    with as_user(conn, "u1", "viewer"):
        assert conn.execute("select cancel_pipeline_run(%s) as s", (rid,)).fetchone()["s"] == "cancelled"
    w = worker(conn, provider, tmp_path, datetime.now(UTC))
    w.drain()
    assert (
        conn.execute("select status from pipeline_runs where pipeline_run_id = %s", (rid,)).fetchone()[
            "status"
        ]
        == "cancelled"
    )
    assert (
        conn.execute(
            "select count(*) as n from pipeline_run_steps where pipeline_run_id = %s", (rid,)
        ).fetchone()["n"]
        == 0
    )

    # during: the run is cancelled while the snapshot step runs; later steps are skipped, the snapshot stays
    rid2, _ = request(conn, "r1", "researcher", mode="replay", as_of=SLOT)
    real = orch.build_snapshot

    def cancelling(*a, **k):  # type: ignore[no-untyped-def]
        out = real(*a, **k)
        conn.execute("update pipeline_runs set status = 'cancelled' where pipeline_run_id = %s", (rid2,))
        return out

    monkeypatch.setattr(orch, "build_snapshot", cancelling)
    worker(conn, provider, tmp_path, SLOT + timedelta(seconds=1)).drain()
    steps = {
        s["step"]: s["status"]
        for s in conn.execute("select * from pipeline_run_steps where pipeline_run_id = %s", (rid2,))
    }
    assert steps["build_snapshot"] == "succeeded"
    assert {steps[k] for k in ("readiness_check", "infer", "publish", "schedule_settlement")} == {"skipped"}
    assert (
        conn.execute("select status from pipeline_runs where pipeline_run_id = %s", (rid2,)).fetchone()[
            "status"
        ]
        == "cancelled"
    )
    assert conn.execute("select count(*) as n from security_state_snapshots").fetchone()["n"] == 1
    assert conn.execute("select count(*) as n from predictions").fetchone()["n"] == 0


def test_predictions_follow_display_tier(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    request(conn, "r1", "researcher", mode="replay", as_of=SLOT)
    worker(conn, provider, tmp_path, SLOT + timedelta(seconds=1)).drain()
    tiers = {r["display_tier"] for r in conn.execute("select display_tier from predictions")}
    shadow = sum(1 for _ in conn.execute("select 1 from predictions where display_tier = 'internal_shadow'"))
    with as_user(conn, "u1", "viewer"):
        seen = conn.execute("select count(*) as n from predictions").fetchone()["n"]
        stl = conn.execute("select count(*) as n from prediction_settlements").fetchone()["n"]
    with as_user(conn, "r1", "researcher"):
        all_ = conn.execute("select count(*) as n from predictions").fetchone()["n"]
    assert tiers and all_ == 2 and seen == all_ - shadow and stl == 0


def test_refresh_reuses_a_valid_snapshot_or_queues_one(conn) -> None:  # type: ignore[no-untyped-def]
    with as_user(conn, "u1", "viewer"):
        a = conn.execute("select * from request_refresh('sec_nvda')").fetchone()
        b = conn.execute("select * from request_refresh('sec_nvda')").fetchone()
    assert a["job_id"] and a["job_id"] == b["job_id"] and a["reused_snapshot_id"] is None
    with pytest.raises(psycopg.errors.InvalidParameterValue), as_user(conn, "u1", "viewer"):
        conn.execute("select * from request_refresh('sec_qqq')")  # reference ETF: not covered
