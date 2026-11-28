"""Replay one trading day end to end (DP 1.17; OQ-51): at every sched-0.1 intraday slot run the pipeline in
`replay` mode with a provider that only knows data up to that slot (trigger `scheduled` -> primary slot samples),
then, after the close, settle every published prediction with the quotes received by then, and write the
line-by-line report (Markdown + HTML).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sr.calendar import get_calendar
from sr.calendar.schedule import schedule_slots
from sr.config import load, repo_root
from sr.db import Conn
from sr.marketdata.quote_rules import evaluate_quotes
from sr.pipeline.orchestrator import RunContext, run_pipeline
from sr.replay.report import day_report, to_html
from sr.settle.settle import SettleResult, settle, weights_for

PHASE1_TARGETS = ("regular_60m", "regular_60m_move")


@dataclass(frozen=True)
class DayReplay:
    pipeline_run_ids: list[str]
    settlements: dict[str, SettleResult]
    markdown_path: Path
    html_path: Path
    reports: list[dict[str, Any]]


def replay_day(
    conn: Conn,
    security_id: str,
    session_date: date,
    context_at: Callable[[datetime], RunContext],
    provider_at: Callable[[datetime], Any],
    out_dir: Path | None = None,
    settle_after: timedelta = timedelta(minutes=5),
) -> DayReplay:
    """`context_at(t)` / `provider_at(t)`: a pipeline context / market-data provider that only knows data up to t."""
    session = get_calendar().session(session_date)
    if not session.is_open or session.close_at is None:
        raise ValueError(f"{session_date} is not a trading day")
    runs = []
    for s in schedule_slots(session_date):
        targets = [t for t in s.target_ids if t in PHASE1_TARGETS]
        if s.status != "scheduled" or not targets:
            continue
        res = run_pipeline(
            conn,
            [security_id],
            targets,
            "replay",
            s.scheduled_for,
            context_at(s.scheduled_for),
            trigger_type="scheduled",
        )
        runs.append(res.pipeline_run_id)

    # settle after the close with what had arrived by then
    t_settle = session.close_at + settle_after
    provider = provider_at(t_settle)
    warm = timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
    out: dict[str, SettleResult] = {}
    preds = conn.execute(
        """select p.* from predictions p join prediction_runs r using (run_id) join security_state_snapshots s on s.snapshot_id = r.snapshot_id
            where p.security_id = %s and s.session_date = %s and p.status in ('published', 'awaiting_settlement') order by p.published_at""",
        (security_id, session_date),
    ).fetchall()
    for p in preds:
        w = weights_for(conn, p["locked"]["benchmark_version_id"])
        start = p["published_at"] - warm
        end = min(p["published_at"] + timedelta(minutes=62), t_settle)
        q = evaluate_quotes(provider.quotes_1s([security_id, *w], start, end))
        q = q[q["received_at"] <= t_settle].reset_index(drop=True)
        out[p["prediction_id"]] = settle(conn, p["prediction_id"], q, t_settle)

    md, reps = day_report(conn, security_id, session_date)
    d = out_dir or repo_root() / "data" / "replay"
    d.mkdir(parents=True, exist_ok=True)
    mdp = d / f"{security_id}_{session_date.isoformat()}.md"
    hp = d / f"{security_id}_{session_date.isoformat()}.html"
    mdp.write_text(md)
    hp.write_text(to_html(md.split("\n## "), f"replay {security_id} {session_date}"))
    return DayReplay(runs, out, mdp, hp, reps)
