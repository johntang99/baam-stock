"""`uv run sr …` — Phase 0 utilities. replay/settle/train/run arrive in Phase 1 (DP 1.16)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from sr.calendar import get_calendar, schedule_slots

PHASE1 = ("replay", "settle", "train", "run", "report")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sr", description="baam-stock research services (research only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calendar", help="XNYS session for a date (UTC)")
    c.add_argument("date", type=date.fromisoformat)
    s = sub.add_parser("schedule", help="expand sched-0.1 slots for a date")
    s.add_argument("date", type=date.fromisoformat)
    for name in PHASE1:
        sub.add_parser(name, help="Phase 1 (not implemented yet)")
    a = ap.parse_args(argv)
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
    print(f"`sr {a.cmd}` is a Phase 1 command (DP 1.16) and is not implemented in Phase 0.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
