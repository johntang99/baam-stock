"""DP 2.02 job queue + worker: idempotent enqueue, SKIP LOCKED, backoff, dead letter, lock reclaim (OQ-58)."""

from datetime import UTC, datetime, timedelta

import pytest

from sr.jobs.queue import backoff, claim, complete, counts, enqueue, fail
from sr.jobs.scheduler import enqueue_session
from sr.jobs.worker import Worker

T = datetime(2026, 12, 1, 15, 0, tzinfo=UTC)


def test_enqueue_is_idempotent(conn) -> None:  # type: ignore[no-untyped-def]
    a, made = enqueue(conn, "settle_due", {"prediction_id": "pred_x"}, "settle_due|pred_x", T)
    b, again = enqueue(conn, "settle_due", {"prediction_id": "other"}, "settle_due|pred_x", T)
    assert made and not again and a == b
    row = conn.execute("select payload from jobs where job_id = %s", (a,)).fetchone()
    assert row["payload"] == {"prediction_id": "pred_x"}  # unchanged


def test_claim_respects_run_after_and_skip_locked(conn, db_url) -> None:  # type: ignore[no-untyped-def]
    from sr.db import connect

    j1, _ = enqueue(conn, "settle_due", {}, "k1", T)
    j2, _ = enqueue(conn, "settle_due", {}, "k2", T + timedelta(seconds=1))
    enqueue(conn, "settle_due", {}, "k3", T + timedelta(minutes=10))  # not due
    other = connect(db_url)  # a second worker holding a row lock in an open transaction
    try:
        other.execute("select * from jobs where job_id = %s for update", (j1,))
        got = claim(conn, "w1", T + timedelta(seconds=5), limit=5)
        assert [j.job_id for j in got] == [j2]  # j1 is locked: skipped, not waited on
    finally:
        other.rollback()
        other.close()
    got = claim(conn, "w1", T + timedelta(seconds=5), limit=5)
    assert [j.job_id for j in got] == [j1] and got[0].attempts == 1
    assert claim(conn, "w2", T + timedelta(seconds=5)) == []


def test_backoff_then_dead_letter_with_alert(conn) -> None:  # type: ignore[no-untyped-def]
    jid, _ = enqueue(conn, "settle_due", {}, "k", T, max_attempts=3)
    now, waits = T, []
    for _ in range(3):
        (j,) = claim(conn, "w", now)
        st = fail(conn, j, "w", "boom", now)
        r = conn.execute("select status, run_after from jobs where job_id = %s", (jid,)).fetchone()
        waits.append((st, (r["run_after"] - now).total_seconds()))
        now = r["run_after"]
    assert waits[0] == ("retry_wait", 30.0) and waits[1] == ("retry_wait", 60.0)  # 2^n x 15 s
    assert waits[2][0] == "dead"
    assert claim(conn, "w", now + timedelta(hours=2)) == []  # dead jobs are never claimed
    alert = conn.execute("select * from alerts where ref = %s", (jid,)).fetchone()
    assert alert["kind"] == "pipeline_failed" and alert["severity"] == "warning"
    assert backoff(20).total_seconds() == 3600  # capped


def test_crashed_worker_lock_is_reclaimed(conn) -> None:  # type: ignore[no-untyped-def]
    jid, _ = enqueue(conn, "settle_due", {}, "k", T)
    (j,) = claim(conn, "dead-worker", T)
    assert claim(conn, "w2", T + timedelta(minutes=4)) == []  # lock still fresh
    (j2,) = claim(conn, "w2", T + timedelta(minutes=6))  # older than 5 minutes: reclaimed
    assert j2.job_id == jid and j2.attempts == 2
    complete(conn, jid, "dead-worker")  # the old worker can no longer complete it
    assert conn.execute("select status from jobs where job_id = %s", (jid,)).fetchone()["status"] == "running"
    complete(conn, jid, "w2")
    assert counts(conn) == {"succeeded": 1}


def test_worker_commits_work_with_completion_or_rolls_both_back(conn) -> None:  # type: ignore[no-untyped-def]
    enqueue(conn, "settle_due", {"ok": True}, "good", T)
    enqueue(conn, "settle_due", {"ok": False}, "bad", T)
    enqueue(conn, "train", {}, "nohandler", T)

    def handler(c, job, now):  # type: ignore[no-untyped-def]
        c.execute(
            "insert into alerts (alert_id, severity, kind, opened_at, message) values (%s, 'info', 'drift', %s, 'x')",
            (f"a_{job.job_id}", now),
        )
        if not job.payload["ok"]:
            raise RuntimeError("handler failed")

    w = Worker(conn, {"settle_due": handler}, clock=lambda: T, worker_id="w")
    recs = w.drain()
    assert sorted(r.status for r in recs) == ["retry_wait", "succeeded"]
    assert (
        conn.execute("select count(*) as n from alerts").fetchone()["n"] == 1
    )  # the failed try left nothing
    st = {r["idempotency_key"]: r["status"] for r in conn.execute("select idempotency_key, status from jobs")}
    assert st == {
        "good": "succeeded",
        "bad": "retry_wait",
        "nohandler": "queued",
    }  # not claimed without a handler
    bad = conn.execute("select last_error from jobs where idempotency_key = 'bad'").fetchone()
    assert "handler failed" in bad["last_error"]


@pytest.mark.parametrize("slots", [False, True])
def test_scheduler_queues_a_session_once(conn, slots) -> None:  # type: ignore[no-untyped-def]
    from datetime import date

    secs = ["sec_nvda", "sec_amd", "sec_avgo", "sec_mu"]
    n1 = enqueue_session(conn, date(2026, 12, 1), secs, slots=slots)
    assert n1["build_snapshot"] == 4 * 80  # 78 x 5-minute + 2 session checks (D-17)
    assert n1["run_forecast"] == (4 * 6 if slots else 0)  # sched-0.1 slots (D-43)
    n2 = enqueue_session(conn, date(2026, 12, 1), secs, slots=slots)
    assert (
        n2["build_snapshot"] == n2["run_forecast"] == 0
        and n2["existing"] == n1["build_snapshot"] + n1["run_forecast"]
    )
    assert enqueue_session(conn, date(2026, 12, 5), secs)["build_snapshot"] == 0  # Saturday
