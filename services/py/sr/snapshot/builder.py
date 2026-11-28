"""Security state snapshots (DP 1.10; DC security_state_snapshots; D-17, D-28, D-41; AC-11, AC-12, AC-40; OQ-44).

A snapshot records what was known about one security at `analysis_as_of`: the evidence and market watermarks, the
market state, the day return vs the previous official close (absolute and relative to the peer basket), the event
analyses currently in force, an explanation status and summary, data quality, validity and prediction readiness.

Same-watermark merge (D-17): `dedupe_key = security | evidence_watermark | market_watermark (floored to 1 s)`. A
trigger whose inputs did not change returns the snapshot already published for those watermarks; nothing is
written. Snapshots are append-only (DB trigger).

Point in time: quotes received after `analysis_as_of` raise LookaheadError; evidence, analyses and collection runs
are read with `<= analysis_as_of`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

import pandas as pd

from sr.benchmark.basket import basket_return
from sr.calendar import get_calendar
from sr.calendar.calendar import ET, Session, et_to_utc
from sr.config import load
from sr.db import Conn, jsonb
from sr.events.reaction import persist_quotes, quote_id, quote_row, sync_points
from sr.events.readiness import allowed_models, not_applicable
from sr.ids import new_id
from sr.timeguard import assert_not_after, ensure_utc

STATUS_RANK = {"insufficient": 0, "partial": 1, "supported": 2}


@dataclass(frozen=True)
class Trigger:
    trigger_type: Literal[
        "scheduled", "event", "market_move", "on_demand", "session_check", "user_supplement"
    ]
    trigger_ref: str | None
    analysis_as_of: datetime


@dataclass(frozen=True)
class SnapshotResult:
    status: Literal["published", "merged"]
    snapshot_id: str
    row: dict[str, Any]
    quality_issues: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------- schedule (D-17)
def schedule(session: Session) -> list[Trigger]:
    """5-minute grid from the open to close − 5 min, plus the ET session checks that fall inside the session."""
    if not session.is_open or session.open_at is None or session.close_at is None:
        return []
    cfg = load("snapshot")["schedule"]
    step = timedelta(minutes=int(cfg["every_min"]))
    out, t = [], session.open_at
    while t < session.close_at:
        out.append(Trigger("scheduled", str(cfg["scheduled_ref"]), t))
        t += step
    for hhmm in cfg["session_checks_et"]:
        h, m = (int(x) for x in str(hhmm).split(":"))
        at = et_to_utc(session.session_date, time(h, m))
        if session.open_at <= at < session.close_at:
            out.append(Trigger("session_check", f"check_{h:02d}{m:02d}", at))
    return sorted(out, key=lambda x: (x.analysis_as_of, x.trigger_type != "scheduled"))


def valid_until(as_of: datetime, session: Session) -> datetime:
    """D-41: in regular hours the next scheduled snapshot + 5 min; otherwise the next session's open."""
    cal = get_calendar()
    a = ensure_utc(as_of, "as_of").to_pydatetime()
    if session.is_open and session.open_at and session.close_at and session.open_at <= a < session.close_at:
        nxt = next((t.analysis_as_of for t in schedule(session) if t.analysis_as_of > a), None)
        if nxt is not None:
            return nxt + timedelta(minutes=int(load("snapshot")["valid_until"]["after_next_scheduled_min"]))
    nxt_s = cal.next_open_session_after(
        a
    )  # pre-market -> today's open; after close / closed day -> next open
    assert nxt_s.open_at is not None
    return nxt_s.open_at


def market_state(as_of: datetime, session: Session, latest: dict[str, Any] | None) -> str:
    if latest is not None and (bool(latest.get("halted")) or bool(latest.get("luld_pause"))):
        return "halted"
    if not session.is_open or session.open_at is None or session.close_at is None:
        return "closed"
    a = ensure_utc(as_of, "as_of").to_pydatetime()
    if a < session.open_at:
        return "pre_market"
    return "regular" if a < session.close_at else "post_market"


# ---------------------------------------------------------------- DB reads (point in time)
def benchmark_version(conn: Conn, security_id: str, session_date: date) -> tuple[str, dict[str, float]]:
    bid = f"{load('snapshot')['benchmark_prefix']}{security_id.removeprefix('sec_')}"
    row = conn.execute(
        """select benchmark_version_id, constituents from benchmark_versions
            where benchmark_id = %s and effective_from <= %s and (effective_to is null or effective_to > %s)
            order by version desc limit 1""",
        (bid, session_date, session_date),
    ).fetchone()
    if row is None:
        raise KeyError(f"no benchmark version for {bid} on {session_date}")
    return row["benchmark_version_id"], {c["security_id"]: float(c["weight"]) for c in row["constituents"]}


def evidence_watermark(
    conn: Conn, security_id: str, as_of: datetime, session_date: date
) -> tuple[datetime, list[dict[str, Any]], str | None]:
    """(watermark, quality issues, latest collection run id) — OQ-44."""
    a = ensure_utc(as_of, "as_of").to_pydatetime()
    item = conn.execute(
        """select max(ci.available_at) as wm from collection_items ci
             join collection_runs cr using (collection_run_id)
            where cr.security_id = %s and ci.available_at <= %s and ci.disposition <> 'excluded_after_asof'""",
        (security_id, a),
    ).fetchone()
    run = conn.execute(
        """select collection_run_id, window_to, counts from collection_runs
            where security_id = %s and window_to <= %s order by window_to desc limit 1""",
        (security_id, a),
    ).fetchone()
    issues: list[dict[str, Any]] = []
    if run is not None and int((run["counts"] or {}).get("failed", 0)) > 0:
        issues.append({"issue": "source_fetch_failed", "count": int(run["counts"]["failed"])})
    if item and item["wm"] is not None:
        return item["wm"], issues, run["collection_run_id"] if run else None
    if run is not None:
        return run["window_to"], issues, run["collection_run_id"]
    prev = conn.execute(
        """select evidence_watermark from security_state_snapshots
            where security_id = %s and analysis_as_of <= %s order by analysis_as_of desc limit 1""",
        (security_id, a),
    ).fetchone()
    issues.append({"issue": "no_collection_run"})
    if prev is not None:
        return prev["evidence_watermark"], issues, None
    return datetime.combine(session_date, time(0, 0), tzinfo=ET).astimezone(a.tzinfo), issues, None


def current_analyses(conn: Conn, security_id: str, as_of: datetime, since: datetime) -> list[dict[str, Any]]:
    """Latest analysis per linked event, published by as_of, with analysis_as_of after `since` (OQ-44)."""
    a = ensure_utc(as_of, "as_of").to_pydatetime()
    return list(
        conn.execute(
            """select distinct on (v.event_id) v.analysis_id, v.event_id, v.analysis_as_of, v.published_at,
                      v.market_explanation, v.prediction_readiness, e.category
                 from event_analysis_versions v
                 join event_security_links l on l.event_id = v.event_id and l.security_id = v.security_id
                 join events e on e.event_id = v.event_id
                where v.security_id = %s and v.published_at <= %s and v.analysis_as_of > %s
                order by v.event_id, v.analysis_version desc""",
            (security_id, a, ensure_utc(since, "since").to_pydatetime()),
        ).fetchall()
    )


def _previous_snapshot(conn: Conn, security_id: str, as_of: datetime) -> dict[str, Any] | None:
    return conn.execute(
        """select * from security_state_snapshots where security_id = %s and analysis_as_of < %s
            order by analysis_as_of desc limit 1""",
        (security_id, ensure_utc(as_of, "as_of").to_pydatetime()),
    ).fetchone()


# ---------------------------------------------------------------- build
def dedupe_key(security_id: str, evidence_wm: datetime, market_wm: datetime) -> str:
    mw = ensure_utc(market_wm, "market_watermark").floor("1s")
    return f"{security_id}|{ensure_utc(evidence_wm, 'evidence_watermark').isoformat()}|{mw.isoformat()}"


def _day_returns(
    quotes: pd.DataFrame,
    security_id: str,
    weights: dict[str, float],
    as_of: pd.Timestamp,
    prev_close: Mapping[str, float | None],
    stale: pd.Timedelta,
) -> tuple[float | None, float | None, dict[str, Any] | None, pd.Timestamp | None]:
    """(day_return_pct, day_relative_pp, stock quote row used, its sample ts)."""
    pts = sync_points(quotes, security_id, list(weights), as_of - stale, as_of)
    p0 = prev_close.get(security_id)
    if pts:
        p = pts[-1]
        stock = p.stock
        day = None if not p0 else (float(stock["mid"]) / float(p0) - 1.0) * 100.0
        br = basket_return(
            {c: prev_close.get(c) for c in weights},
            {c: p.constituents.get(c, {}).get("mid") for c in weights},
            weights,
        )
        rel = None if day is None or br.status != "ok" or br.return_pct is None else day - br.return_pct
        return day, rel, stock, p.ts
    q = quotes[
        (quotes["security_id"] == security_id) & quotes["is_qualifying"] & (quotes["ts"] >= as_of - stale)
    ]
    if q.empty:
        return None, None, None, None
    r = q.sort_values("ts").iloc[-1].to_dict()
    day = None if not p0 else (float(r["mid"]) / float(p0) - 1.0) * 100.0
    return day, None, {str(k): v for k, v in r.items()}, r["ts"]


def build_snapshot(
    conn: Conn,
    security_id: str,
    trigger: Trigger,
    quotes: pd.DataFrame,
    prev_close: Mapping[str, float | None],
    published_at: datetime,
    vendor_source_id: str | None = None,
) -> SnapshotResult:
    """`quotes`: evaluated 1-second quotes (stock + basket) received by analysis_as_of. `prev_close`: previous
    session official close per security id (D-11), None where unknown."""
    cfg = load("snapshot")
    as_of = ensure_utc(trigger.analysis_as_of, "analysis_as_of")
    assert_not_after(quotes["received_at"], as_of, "quotes")
    assert_not_after(quotes["ts"], as_of, "quotes")
    cal = get_calendar()
    session = cal.session_for_instant(as_of.to_pydatetime())
    bmv, weights = benchmark_version(conn, security_id, session.session_date)
    stale = pd.Timedelta(seconds=int(cfg["quality"]["stale_after_s"]))
    prev = _previous_snapshot(conn, security_id, as_of.to_pydatetime())

    stock_q = quotes[quotes["security_id"] == security_id].sort_values("ts")
    latest_raw = {str(k): v for k, v in stock_q.iloc[-1].to_dict().items()} if not stock_q.empty else None
    qual = stock_q[stock_q["is_qualifying"]]
    if not qual.empty:
        market_wm = ensure_utc(qual.iloc[-1]["quote_ts"], "quote_ts").to_pydatetime()
    elif prev is not None:
        market_wm = prev["market_watermark"]
    else:  # nothing ever seen: start of the session date (ET), never after as_of
        day0 = datetime.combine(session.session_date, time(0, 0), tzinfo=ET).astimezone(as_of.tzinfo)
        market_wm = min(day0, as_of.to_pydatetime())
    ev_wm, issues, _run = evidence_watermark(conn, security_id, as_of.to_pydatetime(), session.session_date)
    state = market_state(as_of.to_pydatetime(), session, latest_raw)

    key = dedupe_key(security_id, ev_wm, market_wm)
    found = conn.execute("select * from security_state_snapshots where dedupe_key = %s", (key,)).fetchone()
    if found is not None:
        return SnapshotResult(
            "merged", found["snapshot_id"], dict(found), list(found["quality_issues"] or [])
        )

    day, rel, used, used_ts = _day_returns(quotes, security_id, weights, as_of, prev_close, stale)
    regular = state == "regular"

    # data quality (OQ-44; DP 1.23 refines run_state / quality_issues)
    lag = as_of - ensure_utc(market_wm, "market_wm")
    if regular and (session.open_at is None or market_wm < session.open_at):
        quality = "failed"  # no qualifying quote at all in this session
        issues.append({"issue": "no_qualifying_quote"})
    elif regular and lag > stale:
        quality = "stale"
        issues.append({"issue": "stale_quotes", "lag_s": int(lag.total_seconds())})
    elif (regular and rel is None) or any(i["issue"] == "source_fetch_failed" for i in issues):
        quality = "partial"
        if regular and rel is None:
            issues.append({"issue": "previous_close_missing" if day is None else "benchmark_unavailable"})
    else:
        quality = "ok"
    if any(i["issue"] == "no_collection_run" for i in issues) and quality == "ok":
        quality = "partial"
    run_state = {"ok": "complete", "stale": "degraded", "partial": "degraded", "failed": "failed"}[quality]
    last_valid = as_of.to_pydatetime() if quality == "ok" else (prev["last_valid_at"] if prev else None)

    # events in force since the previous regular close
    prev_session = cal.previous_open_session(session.session_date)
    since = prev_session.close_at or (as_of.to_pydatetime() - timedelta(days=1))
    analyses = current_analyses(conn, security_id, as_of.to_pydatetime(), since)
    sm = cfg["summary"]
    if analyses:
        latest = max(analyses, key=lambda r: r["analysis_as_of"])
        ex_status = str((latest["market_explanation"] or {}).get("status", "insufficient"))
        summary = sm["events"].format(n=len(analyses), status=ex_status)
        readiness = dict(latest["prediction_readiness"] or {})
    else:
        ex_status = "partial" if day is not None else "insufficient"
        parts = [sm["no_catalyst"]]
        if rel is not None:
            parts.append(sm["relative_unexplained"].format(rel=rel))
        elif day is not None:
            parts.append(sm["relative_unavailable"])
        else:
            parts.append(sm["no_quotes"])
        summary = "；".join(parts) + "。"
        readiness = {"event_outcome": not_applicable("no_open_outcome_question")}
        ok_inputs = rel is not None and quality in ("ok", "partial")
        readiness["stock_reaction"] = (
            {"status": "ready", "reason": "market_inputs_valid", "allowed_models": allowed_models("none")}
            if ok_inputs
            else {
                "status": "missing_inputs",
                "reason": "market_inputs_invalid",
                "allowed_models": allowed_models("none"),
            }
        )
    if not regular:  # D-28: no regular-session predictions from extended hours
        readiness["stock_reaction"] = not_applicable("outside_regular_session")

    last_qid = None
    if used is not None and used_ts is not None:
        rule_version = str(load("quote_rules")["quote_rule_version"])
        vendor = vendor_source_id or str(load("reaction")["vendor_source_id"])
        persist_quotes(conn, [quote_row(used, used_ts, vendor, rule_version)])
        last_qid = quote_id(security_id, used_ts)

    row = {
        "snapshot_id": new_id("snap"),
        "security_id": security_id,
        "trigger_type": trigger.trigger_type,
        "trigger_ref": trigger.trigger_ref,
        "analysis_as_of": as_of.to_pydatetime(),
        "evidence_watermark": ev_wm,
        "market_watermark": market_wm,
        "market_state": state,
        "session_date": session.session_date,
        "last_quote_id": last_qid,
        "benchmark_version_id": bmv,
        "day_return_pct": None if day is None else round(day, 6),
        "day_relative_pp": None if rel is None else round(rel, 6),
        "event_analysis_ids": sorted(r["analysis_id"] for r in analyses),
        "new_catalyst_found": bool(analyses),
        "explanation_status": ex_status,
        "explanation_summary": summary,
        "data_quality": quality,
        "run_state": run_state,
        "quality_issues": issues,
        "last_valid_at": last_valid,
        "valid_until": valid_until(as_of.to_pydatetime(), session),
        "prediction_readiness": readiness,
        "dedupe_key": key,
        "published_at": ensure_utc(published_at, "published_at").to_pydatetime(),
    }
    casts = {
        "trigger_type": "::trigger_type",
        "market_state": "::market_state",
        "explanation_status": "::explanation_status",
        "data_quality": "::data_quality",
        "run_state": "::run_state",
    }
    cols = list(row)
    vals = [jsonb(row[c]) if c in ("quality_issues", "prediction_readiness") else row[c] for c in cols]
    marks = ", ".join(f"%s{casts.get(c, '')}" for c in cols)
    ins = conn.execute(
        f"insert into security_state_snapshots ({', '.join(cols)}) values ({marks}) "
        "on conflict (dedupe_key) do nothing returning snapshot_id",
        vals,
    ).fetchone()
    if ins is None:  # a concurrent builder published the same watermarks first
        found = conn.execute(
            "select * from security_state_snapshots where dedupe_key = %s", (key,)
        ).fetchone()
        assert found is not None
        return SnapshotResult(
            "merged", found["snapshot_id"], dict(found), list(found["quality_issues"] or [])
        )
    return SnapshotResult("published", row["snapshot_id"], row, issues)


# ---------------------------------------------------------------- replay one session (AC-11)
def previous_closes(provider: Any, security_ids: list[str], session_date: date) -> dict[str, float | None]:
    """Official close of the previous open session per security (D-11); None where the provider has none."""
    prev = get_calendar().previous_open_session(session_date).session_date
    out: dict[str, float | None] = {}
    for sid in security_ids:
        c = provider.get_official_close(sid, prev)
        out[sid] = None if c is None else float(c.price)
    return out


def replay_session(
    conn: Conn,
    provider: Any,
    security_id: str,
    session_date: date,
    prev_close: Mapping[str, float | None] | None = None,
    publish_lag: timedelta = timedelta(milliseconds=600),
) -> list[SnapshotResult]:
    """Build every scheduled / session-check snapshot of one session from a point-in-time provider."""
    from sr.marketdata.quote_rules import evaluate_quotes

    session = get_calendar().session(session_date)
    triggers = schedule(session)
    if not triggers:
        return []
    bmv, weights = benchmark_version(conn, security_id, session_date)
    ids = [security_id, *weights]
    warm = timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
    stale = pd.Timedelta(seconds=int(load("snapshot")["quality"]["stale_after_s"]))
    end = triggers[-1].analysis_as_of
    raw = provider.quotes_1s(ids, triggers[0].analysis_as_of - warm, end)
    q_all = evaluate_quotes(
        raw
    )  # the trailing median spread uses past rows only, so one pass is point-in-time
    closes = dict(prev_close) if prev_close is not None else previous_closes(provider, ids, session_date)
    out = []
    for t in triggers:
        a = pd.Timestamp(t.analysis_as_of)
        q = q_all[(q_all["received_at"] <= a) & (q_all["ts"] <= a) & (q_all["ts"] >= a - stale)]
        out.append(
            build_snapshot(
                conn, security_id, t, q.reset_index(drop=True), closes, t.analysis_as_of + publish_lag
            )
        )
    return out
