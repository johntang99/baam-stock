"""`uv run sr …` — calendar / schedule utilities, `sr run` (DP 1.16, AC-34), `sr replay` and `sr report` (DP 1.17).
settle / train CLIs follow."""

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
    for name in PHASE1:
        sub.add_parser(name, help="Phase 1 (not implemented yet)")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "replay":
        return cmd_replay(a)
    if a.cmd == "report":
        return cmd_report(a)
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


if __name__ == "__main__":
    raise SystemExit(main())
