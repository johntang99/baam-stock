"""One-click pipeline run: collect -> verify -> analyse -> snapshot -> readiness -> infer -> publish -> schedule
settlement (DP 1.16; DC pipeline_runs / pipeline_run_steps; MP §3 B; D-34; AC-34 Phase 1 part; OQ-50).

Modes: `replay` (a historical as_of; every read is point-in-time, the provider refuses later data) and `dry_run`
(every step runs inside a savepoint that is rolled back — only the run and its step rows are kept, as a report;
nothing else is written). `live` behaves like replay with as_of = now.
Reuse (S3§2): with `reuse_if_unchanged`, a run whose snapshot merged into an existing one (same watermarks) and
whose predictions already exist returns them (`outputs.reused = true`) and publishes nothing new;
`force_recompute` publishes separate `on_demand` forecasts. A run that failed part-way resumes from its first
unfinished step when called again with the same inputs (idempotency key); published parts are never rewritten.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from sr.db import Conn, jsonb
from sr.events.explain import publish_explanation, quotes_for
from sr.evidence.collection_log import run_collection
from sr.forecast.publish import publish
from sr.forecast.run import LoadedModels, forecast_snapshot
from sr.ids import new_id
from sr.marketdata.quote_rules import REQUIRED_COLUMNS, evaluate_quotes
from sr.snapshot.builder import Trigger, benchmark_version, build_snapshot, previous_closes
from sr.timeguard import ensure_utc

STEPS = (
    "collect_evidence",
    "verify_dedupe",
    "analyze_events",
    "build_snapshot",
    "readiness_check",
    "infer",
    "publish",
    "schedule_settlement",
)
TARGET_ROWS = {
    "regular_60m": "tgt_regular_60m_v1",
    "regular_60m_move": "tgt_regular_60m_move_v1",
    "regular_to_close": "tgt_regular_to_close_v1",  # no model yet: abstains model_not_validated (OQ-57)
    "next_regular_session": "tgt_next_regular_session_v1",  # likewise
}


class _Rollback(Exception):
    """Raised at the end of a dry run to discard everything written inside the savepoint."""


@dataclass
class RunContext:
    provider: Any  # point-in-time market data (refuses data after its as_of)
    models: LoadedModels
    history: pd.DataFrame  # realised windows (sigma / HAR inputs)
    sources: list[Any] = field(default_factory=list)  # evidence sources; none -> collect step skipped
    storage: Any = None
    prev_close: dict[str, float | None] | None = None
    feature_dir: Path | None = None
    publish_lag: timedelta = timedelta(milliseconds=600)


@dataclass
class PipelineResult:
    pipeline_run_id: str
    status: str
    outputs: dict[str, Any]
    steps: list[dict[str, Any]]
    reused_run: bool = False


def idempotency_key(
    security_ids: list[str], target_ids: list[str], as_of: datetime, mode: str, requested_by: str | None
) -> str:
    t = ensure_utc(as_of, "as_of").floor("1min")
    return f"{','.join(sorted(security_ids))}|{','.join(sorted(target_ids))}|{t.isoformat()}|{mode}|{requested_by or '-'}"


def _snapshot_quotes(provider: Any, ids: list[str], as_of: datetime) -> pd.DataFrame:
    from sr.calendar import get_calendar
    from sr.config import load

    warm = timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
    have = getattr(provider, "security_ids", None)
    session = get_calendar().session_for_instant(as_of)
    start = as_of - warm - timedelta(seconds=60)
    if (
        session.open_at is not None and session.open_at < as_of
    ):  # the market watermark is the day's latest quote
        start = min(start, session.open_at - warm)
    raw = provider.quotes_1s([i for i in ids if have is None or i in have], start, as_of)
    if not set(REQUIRED_COLUMNS) <= set(raw.columns):  # nothing at all in the window (e.g. 08:30 pre-market)
        utc = "datetime64[ns, UTC]"
        raw = pd.DataFrame(
            {
                c: pd.Series(dtype=utc if c in ("ts", "quote_ts", "received_at") else "object")
                for c in (*REQUIRED_COLUMNS, "last")
            }
        )
    q = evaluate_quotes(raw)  # an empty frame still gets the evaluated columns
    a = pd.Timestamp(as_of)
    return q[(q["received_at"] <= a)].reset_index(drop=True)  # build_snapshot looks back as far as it needs


class _Run:
    def __init__(
        self,
        conn: Conn,
        pid: str,
        persist: bool,
        prior: dict[int, dict[str, Any]],
        check_cancel: bool = False,
    ) -> None:
        self.conn, self.pid, self.persist, self.prior = conn, pid, persist, prior
        self.check_cancel = check_cancel
        self.cancelled = False
        self.rows: list[dict[str, Any]] = []

    def _is_cancelled(self) -> bool:
        if not self.check_cancel or self.cancelled:
            return self.cancelled
        r = self.conn.execute(
            "select status from pipeline_runs where pipeline_run_id = %s", (self.pid,)
        ).fetchone()
        self.cancelled = r is not None and r["status"] == "cancelled"
        return self.cancelled

    def step(
        self, no: int, name: str, sec: str, fn: Callable[[], tuple[str, dict[str, Any]]], now: datetime
    ) -> dict[str, Any]:
        if self._is_cancelled():  # cancelled from the page between steps: the rest is skipped, nothing undone
            rec = {
                "step_no": no,
                "step": name,
                "security_id": sec,
                "status": "skipped",
                "attempt": 0,
                "started_at": None,
                "finished_at": None,
                "detail": {"reason": "cancelled"},
                "error": None,
            }
            self.rows.append(rec)
            if self.persist:
                self.conn.execute(
                    """insert into pipeline_run_steps (pipeline_run_id, step_no, step, security_id, status, attempt, detail)
                       values (%s, %s, %s::pipeline_step, %s, 'skipped', 0, %s) on conflict (pipeline_run_id, step_no) do nothing""",
                    (self.pid, no, name, sec, jsonb(rec["detail"])),
                )
            return rec
        done = self.prior.get(no)
        if done and done["status"] in ("succeeded", "skipped") and name not in ("infer",):
            self.rows.append(done)
            return done
        attempt = int(done["attempt"]) + 1 if done else 1
        try:
            status, detail = fn()
            rec = {
                "step_no": no,
                "step": name,
                "security_id": sec,
                "status": status,
                "attempt": attempt,
                "started_at": now,
                "finished_at": now,
                "detail": detail,
                "error": None,
            }
        except Exception as e:  # recorded, then re-raised by the caller's policy (stop this security)
            rec = {
                "step_no": no,
                "step": name,
                "security_id": sec,
                "status": "failed",
                "attempt": attempt,
                "started_at": now,
                "finished_at": now,
                "detail": {},
                "error": {"code": type(e).__name__, "message": str(e)[:500]},
            }
        self.rows.append(rec)
        if self.persist:
            self.conn.execute(
                """insert into pipeline_run_steps (pipeline_run_id, step_no, step, security_id, status, attempt, started_at,
                       finished_at, detail, error)
                   values (%s, %s, %s::pipeline_step, %s, %s::pipeline_step_status, %s, %s, %s, %s, %s)
                   on conflict (pipeline_run_id, step_no) do update set status = excluded.status, attempt = excluded.attempt,
                       started_at = excluded.started_at, finished_at = excluded.finished_at, detail = excluded.detail,
                       error = excluded.error""",
                (
                    self.pid,
                    no,
                    name,
                    sec,
                    rec["status"],
                    attempt,
                    now,
                    now,
                    jsonb(rec["detail"]),
                    jsonb(rec["error"]) if rec["error"] else None,
                ),
            )
        return rec


def run_pipeline(
    conn: Conn,
    security_ids: list[str],
    target_ids: list[str],
    mode: str,
    as_of: datetime,
    ctx: RunContext,
    trigger_type: str = "on_demand",
    requested_by: str | None = None,
    reuse_policy: str = "reuse_if_unchanged",
) -> PipelineResult:
    if mode not in ("replay", "dry_run", "live"):
        raise ValueError(f"mode {mode!r} is not supported in Phase 1")
    unknown = [t for t in target_ids if t not in TARGET_ROWS]
    if unknown:
        raise ValueError(f"targets {unknown} are not built yet (supported: {list(TARGET_ROWS)})")
    t = ensure_utc(as_of, "as_of").to_pydatetime()
    key = idempotency_key(security_ids, target_ids, t, mode, requested_by)
    old = conn.execute("select * from pipeline_runs where idempotency_key = %s", (key,)).fetchone()
    prior: dict[int, dict[str, Any]] = {}
    queued = old is not None and old["status"] == "queued"  # requested from the page (request_pipeline_run)
    if old is not None and old["status"] == "cancelled":
        steps = [
            dict(r)
            for r in conn.execute(
                "select * from pipeline_run_steps where pipeline_run_id = %s order by step_no",
                (old["pipeline_run_id"],),
            ).fetchall()
        ]
        return PipelineResult(old["pipeline_run_id"], "cancelled", old["outputs"], steps, reused_run=True)
    if queued:
        assert old is not None
        pid = old["pipeline_run_id"]
        conn.execute(
            "update pipeline_runs set status = 'running', started_at = %s where pipeline_run_id = %s and status = 'queued'",
            (t, pid),
        )
    elif old is not None:
        steps = [
            dict(r)
            for r in conn.execute(
                "select * from pipeline_run_steps where pipeline_run_id = %s order by step_no",
                (old["pipeline_run_id"],),
            ).fetchall()
        ]
        if old["status"] in ("succeeded", "partial") or mode == "dry_run":
            return PipelineResult(
                old["pipeline_run_id"], old["status"], old["outputs"], steps, reused_run=True
            )
        prior = {s["step_no"]: s for s in steps}  # failed / cancelled: resume
        pid = old["pipeline_run_id"]
        conn.execute("update pipeline_runs set status = 'running' where pipeline_run_id = %s", (pid,))
    else:
        pid = new_id("pr")
        if mode != "dry_run":
            conn.execute(
                """insert into pipeline_runs (pipeline_run_id, security_ids, target_ids, trigger_type, requested_by, mode, as_of,
                       status, reuse_policy, started_at, idempotency_key)
                   values (%s, %s, %s::target_id[], %s::pipeline_trigger_type, %s, %s::pipeline_mode, %s, 'running',
                           %s::reuse_policy, %s, %s)""",
                (pid, security_ids, target_ids, trigger_type, requested_by, mode, t, reuse_policy, t, key),
            )
    run = _Run(conn, pid, persist=mode != "dry_run", prior=prior, check_cancel=mode != "dry_run")
    outputs: dict[str, Any] = {"snapshot_ids": [], "prediction_ids": [], "abstained": [], "reused": False}
    failed = False

    def body() -> None:
        nonlocal failed
        for i, sec in enumerate(security_ids):
            if not _one_security(
                conn, run, i, sec, target_ids, mode, t, ctx, trigger_type, reuse_policy, pid, outputs
            ):
                failed = True

    if mode == "dry_run":
        try:
            with conn.transaction():
                body()
                raise _Rollback
        except _Rollback:
            pass
    else:
        body()
    status = "failed" if failed else ("partial" if outputs["abstained"] else "succeeded")
    if run.cancelled:
        status = "cancelled"
    if mode == "dry_run" and queued:  # the queued row exists: keep it, write the report steps under it
        conn.execute(
            "update pipeline_runs set status = %s::pipeline_status, outputs = %s, finished_at = %s where pipeline_run_id = %s",
            (status, jsonb(outputs), t, pid),
        )
        for r in run.rows:
            conn.execute(
                """insert into pipeline_run_steps (pipeline_run_id, step_no, step, security_id, status, attempt, started_at,
                       finished_at, detail, error) values (%s, %s, %s::pipeline_step, %s, %s::pipeline_step_status, %s, %s, %s, %s, %s)
                   on conflict (pipeline_run_id, step_no) do nothing""",
                (
                    pid,
                    r["step_no"],
                    r["step"],
                    r["security_id"],
                    r["status"],
                    r["attempt"],
                    r["started_at"],
                    r["finished_at"],
                    jsonb(r["detail"]),
                    jsonb(r["error"]) if r["error"] else None,
                ),
            )
    elif mode == "dry_run":  # the report: the run and its steps only
        conn.execute(
            """insert into pipeline_runs (pipeline_run_id, security_ids, target_ids, trigger_type, requested_by, mode, as_of, status,
                   reuse_policy, outputs, started_at, finished_at, idempotency_key)
               values (%s, %s, %s::target_id[], %s::pipeline_trigger_type, %s, 'dry_run', %s, %s::pipeline_status, %s::reuse_policy,
                       %s, %s, %s, %s)""",
            (
                pid,
                security_ids,
                target_ids,
                trigger_type,
                requested_by,
                t,
                status,
                reuse_policy,
                jsonb(outputs),
                t,
                t,
                key,
            ),
        )
        for r in run.rows:
            conn.execute(
                """insert into pipeline_run_steps (pipeline_run_id, step_no, step, security_id, status, attempt, started_at,
                       finished_at, detail, error) values (%s, %s, %s::pipeline_step, %s, %s::pipeline_step_status, %s, %s, %s, %s, %s)""",
                (
                    pid,
                    r["step_no"],
                    r["step"],
                    r["security_id"],
                    r["status"],
                    r["attempt"],
                    r["started_at"],
                    r["finished_at"],
                    jsonb(r["detail"]),
                    jsonb(r["error"]) if r["error"] else None,
                ),
            )
    else:  # a run cancelled from the page keeps `cancelled`; published parts stay
        conn.execute(
            """update pipeline_runs set status = %s::pipeline_status, outputs = %s, finished_at = coalesce(finished_at, %s)
                where pipeline_run_id = %s and status <> 'cancelled'""",
            (status, jsonb(outputs), t, pid),
        )
    return PipelineResult(pid, status, outputs, run.rows)


def _one_security(
    conn: Conn,
    run: _Run,
    i: int,
    sec: str,
    target_ids: list[str],
    mode: str,
    t: datetime,
    ctx: RunContext,
    trigger_type: str,
    reuse_policy: str,
    pid: str,
    outputs: dict[str, Any],
) -> bool:
    base = i * len(STEPS)
    state: dict[str, Any] = {}
    pub_at = t + ctx.publish_lag

    def collect() -> tuple[str, dict[str, Any]]:
        if not ctx.sources:
            return "skipped", {"reason": "no_sources_configured"}
        last = conn.execute(
            "select max(window_to) as w from collection_runs where security_id = %s and window_to <= %s",
            (sec, t),
        ).fetchone()
        wf = last["w"] if last and last["w"] else t - timedelta(days=1)
        res = run_collection(conn, sec, ctx.sources, wf, t, storage=ctx.storage, pipeline_run_id=pid, now=t)
        state["collection"] = res
        return "succeeded", {"collection_run_id": res.collection_run_id, "counts": res.counts}

    def verify() -> tuple[str, dict[str, Any]]:
        res = state.get("collection")
        if res is None:
            return "skipped", {"reason": "no_collection_run"}
        c = res.counts
        return "succeeded", {
            k: c.get(k, 0) for k in ("fetched", "kept", "duplicate", "excluded", "pending_review", "failed")
        }

    def analyze() -> tuple[str, dict[str, Any]]:
        evs = conn.execute(
            """select distinct l.event_id from event_security_links l join event_evidence e on e.event_id = l.event_id
                where l.security_id = %s and e.available_at <= %s order by 1""",
            (sec, t),
        ).fetchall()
        if not evs:
            return "skipped", {"reason": "no_events_with_evidence"}
        _, w = benchmark_version(conn, sec, get_session_date(t))
        ids = []
        for ev in evs:
            from sr.events.explain import anchor_at, evidence_for

            anchor = anchor_at(evidence_for(conn, ev["event_id"], t))
            q = quotes_for(ctx.provider, sec, list(w), t, anchor)
            out = publish_explanation(conn, ev["event_id"], sec, t, pub_at, q, weights=w)
            if out.publish.analysis_id:
                ids.append(out.publish.analysis_id)
        return "succeeded", {"analysis_ids": ids}

    def snapshot() -> tuple[str, dict[str, Any]]:
        _, w = benchmark_version(conn, sec, get_session_date(t))
        q = _snapshot_quotes(ctx.provider, [sec, *w], t)
        closes = (
            ctx.prev_close
            if ctx.prev_close is not None
            else previous_closes(ctx.provider, [sec, *w], get_session_date(t))
        )
        trig = Trigger(trigger_type, pid, t)  # type: ignore[arg-type]  # pipeline trigger types are snapshot trigger types
        r = build_snapshot(conn, sec, trig, q, closes, t + timedelta(milliseconds=300))
        state["snapshot_id"], state["merged"] = r.snapshot_id, r.status == "merged"
        outputs["snapshot_ids"].append(r.snapshot_id)
        return "succeeded", {"snapshot_id": r.snapshot_id, "merged": state["merged"]}

    def readiness() -> tuple[str, dict[str, Any]]:
        s = conn.execute(
            "select * from security_state_snapshots where snapshot_id = %s", (state["snapshot_id"],)
        ).fetchone()
        assert s is not None
        return "succeeded", {
            "market_state": s["market_state"],
            "data_quality": s["data_quality"],
            "stock_reaction": (s["prediction_readiness"] or {}).get("stock_reaction"),
        }

    def existing() -> list[dict[str, Any]]:
        """Predictions already made from this snapshot for these targets. A scheduled slot reuses only a prediction
        made for that same slot, so an unchanged snapshot never swallows a later slot (AC-52)."""
        rows = conn.execute(
            """select p.prediction_id, p.target_row_id, p.status, p.abstain_reason, p.scheduled_for from predictions p
                 join prediction_runs r using (run_id) where r.snapshot_id = %s and p.target_row_id = any(%s)""",
            (state["snapshot_id"], [TARGET_ROWS[x] for x in target_ids]),
        ).fetchall()
        out = [dict(r) for r in rows]
        if trigger_type == "scheduled":
            out = [r for r in out if r["scheduled_for"] == t]
        return out

    def infer() -> tuple[str, dict[str, Any]]:
        if reuse_policy == "reuse_if_unchanged" and state.get("merged") and existing():
            state["reused"] = existing()
            return "skipped", {
                "reason": "inputs_unchanged",
                "reused_prediction_ids": [r["prediction_id"] for r in state["reused"]],
            }
        res = forecast_snapshot(
            conn,
            state["snapshot_id"],
            ctx.provider,
            ctx.models,
            ctx.history,
            pub_at,
            feature_dir=ctx.feature_dir,
            publish_now=False,
            force_recompute_tag=pid if reuse_policy == "force_recompute" else None,
            targets=target_ids,
            trigger_type=trigger_type,
            trigger_at=t,
        )
        rows = {TARGET_ROWS[x] for x in target_ids}
        keep = [p for p in res.predictions if p["target_row_id"] in rows]
        runs = [r for r in res.runs if r["run_id"] in {p["run_id"] for p in keep}]
        state["runs"], state["preds"] = runs, keep
        return "succeeded", {
            "targets": sorted(target_ids),
            "statuses": {p["target_row_id"]: p["status"] for p in keep},
            "abstained": {p["target_row_id"]: p["abstain_reason"] for p in keep if p["abstain_reason"]},
        }

    def do_publish() -> tuple[str, dict[str, Any]]:
        if "reused" in state:
            preds = state["reused"]
            outputs["reused"] = True
            outputs["prediction_ids"] += [p["prediction_id"] for p in preds]
            outputs["abstained"] += [
                {"security_id": sec, "target_id": p["target_row_id"], "reason": p["abstain_reason"]}
                for p in preds
                if p["abstain_reason"]
            ]
            return "skipped", {"reason": "reused", "prediction_ids": [p["prediction_id"] for p in preds]}
        preds = state["preds"]
        outputs["abstained"] += [
            {"security_id": sec, "target_id": p["target_row_id"], "reason": p["abstain_reason"]}
            for p in preds
            if p["abstain_reason"]
        ]
        if mode == "dry_run":
            outputs["prediction_ids"] += [p["prediction_id"] for p in preds]  # would-be ids (not written)
            return "skipped", {"reason": "dry_run", "would_publish": [p["prediction_id"] for p in preds]}
        pub = publish(conn, state["runs"], preds)
        outputs["prediction_ids"] += pub.prediction_ids
        state["published"] = pub.prediction_ids
        return "succeeded", {
            "prediction_ids": pub.prediction_ids,
            "run_ids": pub.run_ids,
            "reused": pub.reused,
        }

    def schedule() -> tuple[str, dict[str, Any]]:
        ids = state.get("published") or []
        if not ids:
            return "skipped", {"reason": "nothing_published"}
        rows = conn.execute(
            "select prediction_id, valid_until from predictions where prediction_id = any(%s) and status = 'published'",
            (ids,),
        ).fetchall()
        jobs = []
        for r in rows:
            jid = new_id("job")
            conn.execute(
                """insert into jobs (job_id, job_type, pipeline_run_id, payload, idempotency_key, run_after)
                   values (%s, 'settle_due', %s, %s, %s, %s) on conflict (idempotency_key) do nothing""",
                (
                    jid,
                    pid,
                    jsonb({"prediction_id": r["prediction_id"]}),
                    f"settle_due|{r['prediction_id']}",
                    r["valid_until"] + timedelta(seconds=30),
                ),
            )
            jobs.append(r["prediction_id"])
        return "succeeded", {"settle_jobs_for": jobs}

    fns = (collect, verify, analyze, snapshot, readiness, infer, do_publish, schedule)
    for k, (name, fn) in enumerate(zip(STEPS, fns, strict=True), start=1):
        rec = run.step(base + k, name, sec, fn, t)
        if rec["status"] == "failed":
            for j, rest in enumerate(STEPS[k:], start=k + 1):  # later steps of this security do not run
                run.rows.append(
                    {
                        "step_no": base + j,
                        "step": rest,
                        "security_id": sec,
                        "status": "pending",
                        "attempt": 0,
                        "started_at": None,
                        "finished_at": None,
                        "detail": {},
                        "error": None,
                    }
                )
            return False
        if name == "build_snapshot" and "snapshot_id" not in state and rec["detail"].get("snapshot_id"):
            state["snapshot_id"], state["merged"] = (
                rec["detail"]["snapshot_id"],
                rec["detail"].get("merged", False),
            )  # resumed
            outputs["snapshot_ids"].append(state["snapshot_id"])
    return True


def get_session_date(t: datetime) -> Any:
    from sr.calendar import get_calendar

    return get_calendar().session_for_instant(t).session_date
