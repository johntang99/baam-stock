"""Training dataset versions (DP 1.11; DC training_dataset_versions §8.3; D-19, D-20, D-23, D-09; OQ-45).

Rows are built day by day, in time order, for each security with a peer-basket benchmark version:
  sample time = each 5-minute grid time of the regular session (publish proxy); D-18 availability must pass;
  label = sr.labels.window (t0 / end sync quotes, relative return); direction class by k × sigma-0.1, where sigma
  uses only windows from earlier sessions; `regular_60m_move` uses |relative return|;
  features = fs-0.2 at the sample time, from 1-minute mids labelled by minute END (so a bar is only visible once
  complete) — every feature function refuses data after its as_of.
Then: event clusters (D-19), `news_time_unknown`, time-ordered splits with a 1-trading-day embargo, cluster
integrity across boundaries, exclusion counts, an availability audit, a Parquet manifest and one
`training_dataset_versions` row. Nothing is ever updated: a new build is a new version (parent link optional).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sr.calendar import get_calendar, is_target_available
from sr.calendar.calendar import ET, Session
from sr.config import load, repo_root
from sr.db import Conn, jsonb
from sr.features.calendar_feats import calendar_features
from sr.features.cross_asset import cross_asset_features
from sr.features.lead_lag import lead_lag_features
from sr.features.vol_regime import vol_regime_features
from sr.ids import new_id
from sr.labels.sigma import estimate_sigma
from sr.labels.thresholds import Abstain, classify, lock_threshold
from sr.labels.window import window_label
from sr.marketdata.quote_rules import evaluate_quotes
from sr.snapshot.builder import benchmark_version
from sr.timeguard import ensure_utc

TARGETS = ("regular_60m", "regular_60m_move")


@dataclass(frozen=True)
class DatasetResult:
    dataset_version_id: str
    row: dict[str, Any]  # the training_dataset_versions row
    frame: pd.DataFrame  # every candidate row with split / exclusion
    manifest_path: str


# ---------------------------------------------------------------- symbols and series
def symbol_of(security_id: str) -> str:
    s = security_id.removeprefix("sec_").upper()
    return "^VIX" if s == "VIX" else s


def security_of(symbol: str) -> str:
    return "sec_" + symbol.lstrip("^").lower()


def minute_mids(q: pd.DataFrame) -> dict[str, pd.Series]:
    """Last valid NBBO mid per minute, indexed by the minute's END (10:19:xx -> 10:20:00)."""
    v = q[q["mid"].notna()]
    out = {}
    for sid, g in v.groupby("security_id"):
        s = g.set_index("ts")["mid"].sort_index()
        m = s.groupby(pd.DatetimeIndex(s.index).floor("1min")).last()
        m.index = m.index + pd.Timedelta(minutes=1)
        out[symbol_of(str(sid))] = m
    return out


def _upto(series: dict[str, pd.Series], t: pd.Timestamp) -> dict[str, pd.Series]:
    return {k: s.loc[:t] for k, s in series.items()}


def features_at(
    series: dict[str, pd.Series], stock_symbol: str, constituents: list[str], t: datetime
) -> dict[str, Any]:
    ts = pd.Timestamp(t)
    s = _upto(series, ts)
    out: dict[str, Any] = dict(calendar_features(t))
    out |= cross_asset_features(s, t)
    out |= lead_lag_features(s, constituents, t)
    stock = s.get(stock_symbol)
    out |= vol_regime_features(
        stock if stock is not None else pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC")), t
    )
    return out


# ---------------------------------------------------------------- events: clusters and unknown times
def _event_sessions(
    conn: Conn, security_id: str, as_of: datetime, sessions: list[Session]
) -> tuple[dict[str, set[date]], set[date]]:
    """({event_id: covered session dates}, session dates with only day/unknown-precision evidence) — OQ-45."""
    cal = get_calendar()
    coarse = set(load("reasoning")["timing"]["coarse_precisions"])
    extend = int(load("dataset")["event_cluster"]["extend_sessions"])
    days = [s.session_date for s in sessions]
    rows = conn.execute(
        """select ev.event_id, ev.available_at, v.source_published_at, v.source_published_precision
             from event_evidence ev
             join event_security_links l on l.event_id = ev.event_id and l.security_id = %s
             join source_document_versions v on v.doc_version_id = ev.doc_version_id
            where ev.available_at <= %s""",
        (security_id, ensure_utc(as_of, "as_of").to_pydatetime()),
    ).fetchall()
    first: dict[str, datetime] = {}
    unknown: set[date] = set()
    for r in rows:
        precise = r["source_published_at"] is not None and r["source_published_precision"] not in coarse
        t = r["source_published_at"] if precise else r["available_at"]
        if not precise:
            unknown.add((r["source_published_at"] or r["available_at"]).astimezone(ET).date())
        first[r["event_id"]] = min(first.get(r["event_id"], t), t)
    cover: dict[str, set[date]] = {}
    for eid, t in first.items():
        s = cal.session_for_instant(t)
        if not (s.is_open and s.close_at is not None and t < s.close_at):
            s = cal.next_open_session_after(t)  # after the close / on a closed day -> the next session
        later = [i for i, d in enumerate(days) if d >= s.session_date]
        if later:
            i = later[0]
            cover[eid] = set(days[i : i + 1 + extend])
    return cover, unknown


def clusters(cover: dict[str, set[date]]) -> dict[date, str]:
    """Merge overlapping event coverages (union-find on shared sessions) -> {session: cluster id}."""
    parent = {e: e for e in cover}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_day: dict[date, list[str]] = {}
    for e, ds in cover.items():
        for d in ds:
            by_day.setdefault(d, []).append(e)
    for es in by_day.values():
        for e in es[1:]:
            a, b = find(es[0]), find(e)
            if a != b:
                parent[max(a, b)] = min(a, b)
    return {d: f"evc:{find(es[0])}" for d, es in by_day.items()}


# ---------------------------------------------------------------- splits (D-19)
def split_days(days: list[date]) -> tuple[dict[date, str], list[dict[str, Any]]]:
    """{day: split name or 'embargo'}, DC `splits` list. Shares of the non-embargo days, each group >= 1 day."""
    cfg = load("dataset")["splits"]
    names, shares, emb = list(cfg["order"]), [float(x) for x in cfg["shares"]], int(cfg["embargo_days"])
    n_emb = emb * (len(names) - 1)
    usable = len(days) - n_emb
    if usable < len(names):
        raise ValueError(f"{len(days)} trading days is too few for {len(names)} splits with embargo")
    sizes = [max(1, math.floor(s * usable)) for s in shares]
    while sum(sizes) > usable:  # rounding up to 1 day each may overshoot: take from the largest
        sizes[sizes.index(max(sizes))] -= 1
    sizes[0] += usable - sum(sizes)  # remainder to train
    out: dict[date, str] = {}
    meta = []
    i = 0
    for k, (name, size) in enumerate(zip(names, sizes, strict=True)):
        group = days[i : i + size]
        for d in group:
            out[d] = name
        i += size
        last = k == len(names) - 1
        meta.append(
            {
                "name": name,
                "start": group[0].isoformat(),
                "end": group[-1].isoformat(),
                "embargo_days": 0 if last else emb,
            }
        )
        if not last:
            for d in days[i : i + emb]:
                out[d] = "embargo"
            i += emb
    return out, meta


# ---------------------------------------------------------------- build
def _sessions(start: date, end: date) -> list[Session]:
    return get_calendar().open_sessions(start, end)


def _grid(s: Session) -> list[datetime]:
    assert s.open_at is not None and s.close_at is not None
    step = timedelta(minutes=int(load("dataset")["sample"]["every_min"]))
    out, t = [], s.open_at
    while t < s.close_at:
        out.append(t)
        t += step
    return out


def build_rows(
    conn: Conn,
    provider: Any,
    securities: Iterable[str],
    start: date,
    end: date,
    target_id: str = "regular_60m",
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """Candidate rows (kept and excluded) before splits. `as_of`: build time — nothing later may be read."""
    if target_id not in TARGETS:
        raise ValueError(f"dataset build supports {TARGETS}, not {target_id!r}")
    cfg = load("dataset")
    sessions = _sessions(start, end)
    if not sessions:
        raise ValueError(f"no open sessions between {start} and {end}")
    last_close = sessions[-1].close_at
    assert last_close is not None
    build_as_of = ensure_utc(as_of or last_close + timedelta(hours=1), "as_of").to_pydatetime()
    if build_as_of < last_close:
        raise ValueError("as_of is before the last session in the dataset has closed")
    refs = [security_of(s) for s in cfg["reference_symbols"]]
    warm = timedelta(minutes=int(load("quote_rules")["qualifying"]["median_spread_window_min"]))
    rows: list[dict[str, Any]] = []
    for sec in securities:
        cover, unknown = _event_sessions(conn, sec, build_as_of, sessions)
        cluster_of = clusters(cover)
        history: list[dict[str, Any]] = []  # realised windows of earlier sessions (sigma input)
        prev_series: dict[str, pd.Series] = {}
        for s in sessions:
            assert s.open_at is not None and s.close_at is not None
            bmv, weights = benchmark_version(conn, sec, s.session_date)
            ids = [sec, *weights, *refs]
            raw = provider.quotes_1s([i for i in ids if _has(provider, i)], s.open_at - warm, s.close_at)
            q = evaluate_quotes(raw) if len(raw) else raw
            day_series = minute_mids(q) if len(q) else {}
            series = {
                k: pd.concat([prev_series[k], v]) if k in prev_series else v for k, v in day_series.items()
            }
            hist_df = pd.DataFrame(history, columns=["window_start", "window_end", "relative_return_pp"])
            constituents = [symbol_of(c) for c in weights]
            day_windows = []
            for t in _grid(s):
                r: dict[str, Any] = {
                    "security_id": sec,
                    "session_date": s.session_date,
                    "sample_ts": t,
                    "benchmark_version_id": bmv,
                    "event_cluster": cluster_of.get(s.session_date),
                    "exclusion": None,
                }
                if s.session_date in unknown:
                    r["exclusion"] = "news_time_unknown"
                av = is_target_available(target_id, t)
                if not av.available:
                    r["exclusion"] = r["exclusion"] or av.abstain_reason
                    rows.append(r)
                    continue
                lab = window_label(q, sec, weights, t, build_as_of, target_id) if len(q) else None
                if lab is None or lab.status != "ok" or lab.relative_return_pp is None:
                    r["exclusion"] = r["exclusion"] or (lab.invalid_reason if lab else "no_sync_start_quote")
                    rows.append(r)
                    continue
                rel = float(lab.relative_return_pp)
                day_windows.append(
                    {"window_start": lab.t0_ts, "window_end": lab.end_ts, "relative_return_pp": rel}
                )
                r |= {
                    "t0_ts": lab.t0_ts,
                    "t0_quote_ts": lab.t0_quote_ts,
                    "end_ts": lab.end_ts,
                    "stock_return_pct": lab.stock_return_pct,
                    "benchmark_return_pct": lab.benchmark_return_pct,
                    "relative_return_pp": rel,
                }
                if target_id == "regular_60m":
                    assert lab.t0_ts is not None
                    sig = estimate_sigma(hist_df, lab.t0_ts.to_pydatetime(), t)
                    lock = lock_threshold(sig.sigma_hat_pp)
                    if isinstance(lock, Abstain):
                        r["exclusion"] = r["exclusion"] or lock.abstain_reason
                    else:
                        r |= {
                            "sigma_hat_pp": lock.sigma_hat_pp,
                            "threshold_pp": lock.threshold_pp,
                            "label": classify(rel, lock.threshold_pp),
                        }
                else:
                    r["label_value"] = abs(rel)
                r |= {f"f_{k}": v for k, v in features_at(series, symbol_of(sec), constituents, t).items()}
                rows.append(r)
            history.extend(day_windows)  # only after the day: sigma never sees same-session windows
            prev_series = {k: v[v.index > (s.close_at - timedelta(minutes=400))] for k, v in series.items()}
    return pd.DataFrame(rows)


def _has(provider: Any, security_id: str) -> bool:
    ids = getattr(provider, "security_ids", None)
    return True if ids is None else security_id in ids


def assign_splits(frame: pd.DataFrame, days: list[date]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    split_of, meta = split_days(days)
    f = frame.copy()
    f["split"] = f["session_date"].map(split_of)
    emb = f["split"] == "embargo"
    f.loc[emb & f["exclusion"].isna(), "exclusion"] = "crosses_split_boundary"
    # an event cluster stays in the group of its first kept row (D-19)
    kept = f[f["exclusion"].isna() & f["event_cluster"].notna()].sort_values("sample_ts")
    home = kept.groupby("event_cluster")["split"].first().to_dict()
    away = f["event_cluster"].notna() & f["exclusion"].isna() & (f["split"] != f["event_cluster"].map(home))
    f.loc[away, "exclusion"] = "crosses_split_boundary"
    return f, meta


def availability_audit(f: pd.DataFrame) -> bool:
    """Every kept row's t0 quote is stamped after its sample time and its window ended by the build; the feature
    functions already raise on anything after the sample time."""
    k = f[f["exclusion"].isna()]
    if k.empty:
        return True
    return bool((k["t0_quote_ts"] > k["sample_ts"]).all() and (k["end_ts"] > k["t0_ts"]).all())


def build_dataset(
    conn: Conn,
    provider: Any,
    securities: list[str],
    start: date,
    end: date,
    target_id: str = "regular_60m",
    as_of: datetime | None = None,
    parent_dataset_version_id: str | None = None,
    out_dir: Path | None = None,
    rows: pd.DataFrame | None = None,
) -> DatasetResult:
    """`rows`: candidate rows from an earlier build_rows call with the same arguments (re-split without
    recomputing labels and features)."""
    cfg = load("dataset")
    frame = (
        rows.copy()
        if rows is not None
        else build_rows(conn, provider, securities, start, end, target_id, as_of)
    )
    days = [s.session_date for s in _sessions(start, end)]
    f, splits = assign_splits(frame, days)
    kept = f[f["exclusion"].isna()]
    ds_id = new_id("ds")
    root = repo_root()
    d = (out_dir or root / cfg["output_dir"]) / ds_id
    d.mkdir(parents=True, exist_ok=True)
    rows_path = d / "rows.parquet"
    f.to_parquet(rows_path, index=False)
    if target_id == "regular_60m":
        counts = Counter(kept["label"]) if len(kept) else Counter()
        total = sum(counts.values())
        balance: dict[str, Any] = {
            c: round(counts.get(c, 0) / total, 6) if total else 0.0
            for c in ("outperform", "flat", "underperform")
        }
    else:
        v = kept["label_value"].to_numpy(dtype=float) if len(kept) else np.array([])
        balance = {
            q: (round(float(np.quantile(v, p)), 6) if len(v) else None)
            for q, p in (("p50", 0.5), ("p80", 0.8), ("p90", 0.9))
        }
    exclusions = {str(k): int(v) for k, v in f["exclusion"].dropna().value_counts().sort_index().items()}
    try:
        manifest_rel = str(d.relative_to(root) / "manifest.json")
    except ValueError:
        manifest_rel = str(d / "manifest.json")
    row = {
        "dataset_version_id": ds_id,
        "target_id": target_id,
        "feature_set_version": load("features/fs-0.2")["feature_set_version"],
        "label_version": cfg["label_version"],
        "source_versions": {
            "dataset_rule": cfg["version"],
            "target_definition_version": load("targets")["target_definition_version"],
            "quote_rule_version": load("quote_rules")["quote_rule_version"],
            "sigma_model_version": load("sigma")["sigma_model_version"],
            "calendar_version": get_calendar().session(days[0]).calendar_version,
            "benchmark_version_ids": sorted(f["benchmark_version_id"].dropna().unique().tolist()),
            "market_data_source": getattr(provider, "source_id", "unknown"),
        },
        "time_range": {"start": days[0].isoformat(), "end": days[-1].isoformat()},
        "splits": splits,
        "availability_check_passed": availability_audit(f),
        "n_rows": int(len(kept)),
        "n_trading_days": int(kept["session_date"].nunique()) if len(kept) else 0,
        "n_event_clusters": int(kept["event_cluster"].dropna().nunique()) if len(kept) else 0,
        "class_balance": balance,
        "exclusions": exclusions,
        "parent_dataset_version_id": parent_dataset_version_id,
        "manifest_path": manifest_rel,
    }
    (d / "manifest.json").write_text(
        json.dumps(
            {**row, "rows_file": "rows.parquet", "synthetic": bool(getattr(provider, "synthetic", False))},
            indent=2,
            default=str,
        )
        + "\n"
    )
    cols = list(row)
    jcols = {"source_versions", "time_range", "splits", "class_balance", "exclusions"}
    conn.execute(
        f"insert into training_dataset_versions ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
        [jsonb(row[c]) if c in jcols else row[c] for c in cols],
    )
    return DatasetResult(ds_id, row, f, manifest_rel)
