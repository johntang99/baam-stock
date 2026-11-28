"""`uv run sr …` — calendar / schedule utilities, `sr run` (DP 1.16, AC-34), `sr replay` and `sr report` (DP 1.17),
`sr live --dry-run` / `sr worker` / `sr quality` (DP 2.01-2.06). settle / train CLIs follow."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any

from sr.calendar import get_calendar, schedule_slots

PHASE1 = ("settle", "train")


def _model_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--direction-model", default=None, help="model_version_id (default: latest market_logit)")
    p.add_argument("--move-model", default=None, help="model_version_id (default: latest gbdt)")
    p.add_argument(
        "--history-dataset", default=None, help="dataset_version_id for realised windows (default: latest)"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sr", description="baam-stock research services")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calendar", help="XNYS session for a date (UTC)")
    c.add_argument("date", type=date.fromisoformat)
    s = sub.add_parser("schedule", help="expand sched-0.1 slots for a date")
    s.add_argument("date", type=date.fromisoformat)
    r = sub.add_parser("run", help="one pipeline run: collect -> ... -> schedule settlement (DP 1.16)")
    r.add_argument("--security", required=True, help="comma-separated security ids, e.g. sec_nvda")
    r.add_argument("--targets", default="regular_60m,regular_60m_move")
    r.add_argument("--mode", choices=["replay", "dry_run"], required=True)
    r.add_argument("--as-of", required=True, help="ISO timestamp with timezone, e.g. 2026-12-01T15:00:00Z")
    r.add_argument("--fixture", required=True, help="Parquet 1-second quote layer (synthetic until D-13)")
    r.add_argument(
        "--reuse-policy", choices=["reuse_if_unchanged", "force_recompute"], default="reuse_if_unchanged"
    )
    _model_args(r)
    rp = sub.add_parser(
        "replay", help="replay one trading day at the sched-0.1 slots, settle, write the report (DP 1.17)"
    )
    rp.add_argument("--security", required=True)
    rp.add_argument("--date", required=True, type=date.fromisoformat)
    rp.add_argument("--fixture", required=True)
    rp.add_argument("--out", default=None, help="report directory (default data/replay)")
    _model_args(rp)
    rr = sub.add_parser("report", help="line-by-line verification report of one prediction (Markdown)")
    rr.add_argument("--prediction", required=True)
    lv = sub.add_parser("live", help="md-ingest + move scanner over the synthetic feed (DP 2.01-2.03)")
    lv.add_argument("--symbols", default="NVDA,AMD,AVGO,MU")
    lv.add_argument(
        "--dry-run", action="store_true", help="no database: ingest, latency, move hits, planned jobs"
    )
    lv.add_argument("--fixture", default="data/fixtures/nvda_2026-12-01_1s.parquet")
    lv.add_argument("--until", default=None, help="ET wall clock HH:MM to stop at (default: the close)")
    lv.add_argument("--flush-dir", default=None, help="write 1-second parts here (default: none in dry run)")
    wk = sub.add_parser("worker", help="run queued jobs (DP 2.02)")
    wk.add_argument("--once", action="store_true", help="drain the due jobs and exit")
    wk.add_argument("--types", default=None, help="comma-separated job types (default: all with a handler)")
    ql = sub.add_parser(
        "quality", help="data-quality report: abstentions and unsettleable by reason (DP 2.06)"
    )
    ql.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    ql.add_argument("--to", dest="end", required=True, type=date.fromisoformat)
    ql.add_argument("--json", action="store_true")
    for name in PHASE1:
        sub.add_parser(name, help="Phase 1 (not implemented yet)")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "replay":
        return cmd_replay(a)
    if a.cmd == "report":
        return cmd_report(a)
    if a.cmd == "live":
        return cmd_live(a)
    if a.cmd == "worker":
        return cmd_worker(a)
    if a.cmd == "quality":
        return cmd_quality(a)
    if a.cmd == "calendar":
        x = get_calendar().session(a.date)
        print(
            json.dumps(
                {
                    "session_date": str(x.session_date),
                    "status": x.status,
                    "open_at": x.open_at.isoformat() if x.open_at else None,
                    "close_at": x.close_at.isoformat() if x.close_at else None,
                    "calendar_version": x.calendar_version,
                    "source": x.source,
                },
                indent=2,
            )
        )
        return 0
    if a.cmd == "schedule":
        for sl in schedule_slots(a.date):
            print(
                f"{sl.slot_id:<15} {sl.time_et} ET  {sl.scheduled_for.isoformat()}  {sl.status:<13} {','.join(sl.target_ids)}"
            )
        return 0
    print(f"`sr {a.cmd}` is a Phase 1 command and is not implemented yet.", file=sys.stderr)
    return 2


def _models_and_history(conn: Any, a: argparse.Namespace) -> tuple[Any, Any]:
    import pandas as pd

    from sr.forecast.run import load_models
    from sr.train.train import load_dataset

    def latest(family: str) -> str:
        row = conn.execute(
            "select model_version_id from model_versions where model_family = %s order by model_version_id desc limit 1",
            (family,),
        ).fetchone()
        if row is None:
            raise SystemExit(f"no {family} model registered; train one first (DP 1.12 / 1.13)")
        return str(row["model_version_id"])

    models = load_models(conn, a.direction_model or latest("market_logit"), a.move_model or latest("gbdt"))
    ds_id = a.history_dataset
    if ds_id is None:
        row = conn.execute(
            "select dataset_version_id from training_dataset_versions where target_id = 'regular_60m' order by created_at desc limit 1"
        ).fetchone()
        ds_id = row["dataset_version_id"] if row else None
    history = (
        load_dataset(conn, ds_id)[1]
        if ds_id
        else pd.DataFrame(columns=["security_id", "session_date", "t0_ts", "end_ts", "relative_return_pp"])
    )
    return models, history


def cmd_run(a: argparse.Namespace) -> int:
    from datetime import datetime

    from sr.db import connect
    from sr.marketdata.providers.fixture import FixtureProvider
    from sr.pipeline.orchestrator import RunContext, run_pipeline

    as_of = datetime.fromisoformat(a.as_of.replace("Z", "+00:00"))
    conn = connect()
    try:
        models, history = _models_and_history(conn, a)
        ctx = RunContext(FixtureProvider(a.fixture, as_of=as_of), models, history)
        res = run_pipeline(
            conn, a.security.split(","), a.targets.split(","), a.mode, as_of, ctx, reuse_policy=a.reuse_policy
        )
        conn.commit()
    finally:
        conn.close()
    print(
        json.dumps(
            {
                "pipeline_run_id": res.pipeline_run_id,
                "status": res.status,
                "outputs": res.outputs,
                "steps": [(s["step_no"], s["step"], s["status"]) for s in res.steps],
            },
            indent=2,
            default=str,
        )
    )
    return 0 if res.status in ("succeeded", "partial") else 1


def cmd_replay(a: argparse.Namespace) -> int:
    from pathlib import Path

    from sr.db import connect
    from sr.marketdata.providers.fixture import FixtureProvider
    from sr.pipeline.orchestrator import RunContext
    from sr.replay.runner import replay_day

    conn = connect()
    try:
        models, history = _models_and_history(conn, a)
        res = replay_day(
            conn,
            a.security,
            a.date,
            lambda t: RunContext(FixtureProvider(a.fixture, as_of=t), models, history),
            lambda t: FixtureProvider(a.fixture, as_of=t),
            out_dir=Path(a.out) if a.out else None,
        )
        conn.commit()
    finally:
        conn.close()
    fails = sum(c["result"] == "FAIL" for r in res.reports for c in r["checks"])
    print(
        json.dumps(
            {
                "pipeline_runs": res.pipeline_run_ids,
                "predictions": len(res.reports),
                "check_failures": fails,
                "markdown": str(res.markdown_path),
                "html": str(res.html_path),
            },
            indent=2,
        )
    )
    return 0 if fails == 0 else 1


def cmd_report(a: argparse.Namespace) -> int:
    from sr.db import connect
    from sr.replay.report import prediction_report, to_markdown

    conn = connect()
    try:
        print(to_markdown(prediction_report(conn, a.prediction)))
    finally:
        conn.close()
    return 0


def cmd_live(a: argparse.Namespace) -> int:
    from datetime import datetime, time, timedelta
    from pathlib import Path

    import pandas as pd

    from sr.calendar.calendar import et_to_utc
    from sr.config import load
    from sr.jobs.handlers import live_snapshot_quotes
    from sr.marketdata.live import LiveIngest, LiveQuoteStore, SimulatedFeed, advance
    from sr.snapshot.builder import schedule
    from sr.snapshot.triggers import MoveScanner

    if not a.dry_run:
        print(
            "live ingest needs the D-13 vendor adapter; only --dry-run on the synthetic feed exists",
            file=sys.stderr,
        )
        return 2
    raw = pd.read_parquet(a.fixture)
    day = raw["ts"].min().tz_convert("America/New_York").date()
    syms = [x.strip() for x in a.symbols.split(",") if x.strip()]
    peers = list(load("benchmarks")["semis_peer_v1"]["constituents"])
    mapping = dict(raw[["symbol", "security_id"]].drop_duplicates().itertuples(index=False, name=None))
    want = {k: v for k, v in mapping.items() if k in set(syms) | set(peers)}
    missing = [x for x in syms if x not in mapping]
    if missing:
        print(f"symbols not in the fixture: {missing}", file=sys.stderr)
        return 2
    s = get_calendar().session(day)
    assert s.open_at is not None and s.close_at is not None
    if a.until:
        hh, mm = (int(x) for x in a.until.split(":"))
        end = et_to_utc(day, time(hh, mm))
    else:
        end = s.close_at
    now = {"t": s.open_at - timedelta(minutes=21)}
    store = LiveQuoteStore(lambda: now["t"], "src_fixture_synthetic", synthetic=True)
    ing = LiveIngest(store, want, flush_dir=Path(a.flush_dir) if a.flush_dir else None)
    feed = SimulatedFeed(raw, want)
    scan = MoveScanner()
    every = timedelta(seconds=float(load("market_move_rules")["scan_every_s"]))
    hits: list[dict[str, Any]] = []
    t: datetime = now["t"]
    nxt = s.open_at
    while t <= end:
        now["t"] = t
        advance(feed, ing, t)
        if s.open_at <= t < s.close_at and t >= nxt:
            ids = sorted(want.values())
            q = live_snapshot_quotes(store, ids, t)
            for sym in syms:
                sec = mapping[sym]
                w = {mapping[p]: 1.0 for p in peers if p != sym}
                w = {k: 1.0 / len(w) for k in w}
                for c in scan.scan(q, sec, t, weights=w):
                    hits.append(
                        {"symbol": sym, "rule_id": c.rule_id, "at": t.isoformat(), "move": c.move_pct}
                    )
            nxt = t + every
        if ing.flush_dir is not None and int(t.timestamp()) % int(load("live")["flush_every_s"]) == 0:
            ing.flush()
        t += timedelta(seconds=5)
    ing.flush()
    trig = [x for x in schedule(s) if x.analysis_as_of <= end]
    out = {
        "synthetic": True,
        "session_date": day.isoformat(),
        "symbols": syms,
        "rows_1s": len(store.frame()),
        "metrics": ing.metrics(now["t"]),
        "move_hits": hits,
        "planned_snapshot_jobs": len(trig) * len(syms),
        "parts": [str(p) for p in ing.parts],
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


def cmd_worker(a: argparse.Namespace) -> int:
    from pathlib import Path

    from sr.config import load, repo_root
    from sr.db import connect
    from sr.jobs.handlers import LiveContext, make_handlers
    from sr.jobs.worker import Worker, system_clock
    from sr.marketdata.live import ParquetQuoteStore

    conn = connect(autocommit=True)
    try:
        store = ParquetQuoteStore(repo_root() / Path(str(load("live")["flush_dir"])), system_clock)
        handlers = make_handlers(LiveContext(store, {}, system_clock))
        handlers.pop(
            "run_forecast"
        )  # slot forecasts need models + history: started by the live scheduler (2.24)
        if a.types:
            keep = set(a.types.split(","))
            handlers = {k: v for k, v in handlers.items() if k in keep}
        w = Worker(conn, handlers)
        if a.once:
            recs = w.drain()
            print(json.dumps([r.__dict__ for r in recs], indent=2, default=str))
            return 0 if all(r.status == "succeeded" for r in recs) else 1
        w.run_forever()
    finally:
        conn.close()
    return 0


def cmd_quality(a: argparse.Namespace) -> int:
    from datetime import UTC, datetime

    from sr.db import connect
    from sr.eval.quality_report import quality_report, to_markdown

    conn = connect()
    try:
        rep = quality_report(conn, a.start, a.end, datetime.now(UTC))
    finally:
        conn.close()
    print(json.dumps(rep, indent=2, default=str) if a.json else to_markdown(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
