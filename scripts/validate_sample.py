"""Sample availability report: coverage, qualifying-quote rate, sync success rate (D-35 thresholds).

Run on the synthetic fixture now and on real vendor samples later (D-13):
  uv run python scripts/validate_sample.py --fixture data/fixtures/nvda_2026-12-01_1s.parquet [--json out.json]
Exit code 0 always (report only) unless --strict, which exits 1 when a D-35 threshold fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta

import pandas as pd

from sr.calendar import get_calendar
from sr.config import load
from sr.marketdata.providers.fixture import FixtureProvider
from sr.marketdata.quote_rules import evaluate_quotes
from sr.marketdata.sync import find_first_sync_qualifying

THRESHOLDS = {"qualifying_quote_pct": 95.0, "sync_success_pct": 95.0}   # D-35 (proposed)


def report(path: str, targets: list[str] | None, step_s: int) -> dict[str, object]:
    prov = FixtureProvider(path)
    df = prov._df  # full sample
    days = sorted(df["ts"].dt.tz_convert("America/New_York").dt.date.unique())
    cal = get_calendar()
    ev = evaluate_quotes(df)
    sync_cfg = load("quote_rules")["sync"]
    peers = load("benchmarks")["semis_peer_v1"]["constituents"]
    sym_of = dict(zip(df["security_id"], df["symbol"], strict=False))
    sid_of = {v: k for k, v in sym_of.items()}

    per_symbol = {}
    for d in days:
        s = cal.session(d)
        if not s.is_open:
            continue
        expected = int((s.close_at - s.open_at).total_seconds()) + 1  # type: ignore[operator]
        for sec, g in ev[ev["ts"].dt.tz_convert("America/New_York").dt.date == d].groupby("security_id"):
            reg = g[(g["ts"] >= s.open_at) & (g["ts"] <= s.close_at)]
            per_symbol[sym_of[sec]] = {
                "coverage_pct": round(100 * reg["ts"].nunique() / expected, 3),
                "qualifying_quote_pct": round(100 * reg["is_qualifying"].mean(), 3),
                "flags": {f: int(sum(f in fl for fl in reg["quality_flags"]))
                          for f in ("stale", "wide_spread", "halted", "luld_pause", "crossed", "delayed")},
            }

    tgts = targets or [t for t in peers if t in sid_of and t in ("NVDA", "AMD", "AVGO", "MU")]
    sync = {}
    for t in tgts:
        basket = [sid_of[c] for c in peers if c != t and c in sid_of]
        ok = total = 0
        for d in days:
            s = cal.session(d)
            if not s.is_open:
                continue
            probe = s.open_at + timedelta(minutes=1)  # type: ignore[operator]
            while probe + timedelta(seconds=int(sync_cfg["start_max_wait_s"])) <= s.close_at:  # type: ignore[operator]
                r = find_first_sync_qualifying(probe, sid_of[t], basket, int(sync_cfg["tolerance_ms"]),
                                               int(sync_cfg["start_max_wait_s"]), quotes=ev)
                ok += r.status == "ok"
                total += 1
                probe += timedelta(seconds=step_s)
        sync[t] = {"checks": total, "sync_success_pct": round(100 * ok / max(total, 1), 3),
                   "basket_size": len(basket)}

    q_overall = round(100 * float(ev["is_qualifying"].mean()), 3)
    s_overall = round(sum(v["sync_success_pct"] for v in sync.values()) / max(len(sync), 1), 3)
    return {
        "sample": path, "synthetic": prov.synthetic, "sessions": [str(d) for d in days],
        "quote_rule_version": load("quote_rules")["quote_rule_version"], "per_symbol": per_symbol, "sync": sync,
        "overall": {"qualifying_quote_pct": q_overall, "sync_success_pct": s_overall},
        "thresholds_d35": THRESHOLDS,
        "pass": {"qualifying_quote_pct": q_overall >= THRESHOLDS["qualifying_quote_pct"],
                 "sync_success_pct": s_overall >= THRESHOLDS["sync_success_pct"]},
        "not_measurable_from_quotes": ["news_time_known_pct", "backfill years (minute >= 3y, second >= 1y)"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True, help="Parquet 1s quote layer (fixture or vendor sample)")
    ap.add_argument("--targets", default="", help="comma-separated tickers (default: pilot names present)")
    ap.add_argument("--step-s", type=int, default=60, help="sync probe spacing in seconds")
    ap.add_argument("--json", default="", help="write the full report as JSON")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    r = report(a.fixture, [x for x in a.targets.split(",") if x] or None, a.step_s)
    tag = "SYNTHETIC (虚构) sample" if r["synthetic"] else "vendor sample"
    print(f"# Sample validation report — {tag}\n\nfile: {r['sample']}  sessions: {', '.join(r['sessions'])}  "
          f"rules: {r['quote_rule_version']}\n")
    print("| symbol | coverage % | qualifying % | stale | wide | halted | luld | crossed | delayed |")
    print("|---|---|---|---|---|---|---|---|---|")
    for sym, v in sorted(r["per_symbol"].items()):  # type: ignore[union-attr]
        f = v["flags"]
        print(f"| {sym} | {v['coverage_pct']} | {v['qualifying_quote_pct']} | {f['stale']} | {f['wide_spread']} | "
              f"{f['halted']} | {f['luld_pause']} | {f['crossed']} | {f['delayed']} |")
    print("\n| target | basket | probes | sync success % |\n|---|---|---|---|")
    for t, v in r["sync"].items():  # type: ignore[union-attr]
        print(f"| {t} | {v['basket_size']} | {v['checks']} | {v['sync_success_pct']} |")
    o, p = r["overall"], r["pass"]
    print(f"\nOverall qualifying {o['qualifying_quote_pct']}% (D-35 ≥ 95%: {'PASS' if p['qualifying_quote_pct'] else 'FAIL'}); "  # type: ignore[index]
          f"sync success {o['sync_success_pct']}% (D-35 ≥ 95%: {'PASS' if p['sync_success_pct'] else 'FAIL'})")  # type: ignore[index]
    print("Not measurable from quotes alone: " + "; ".join(r["not_measurable_from_quotes"]))  # type: ignore[arg-type]
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2, ensure_ascii=False, default=str)
    if a.strict and not all(p.values()):  # type: ignore[union-attr]
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
