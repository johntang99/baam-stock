"""Per-security exposure and impact records (DP 2.05; DC event_analysis_versions.impact; D-42; OQ-61).

One event, several securities, separate records:
- `read_through_links()`: for an event whose subject is company A, every other pilot company whose profile (in force
  at as_of) names A in a relation gets its own link (`competitor`, `supplier`, `customer`). A company with no
  relation gets no link, so an AMD-only order never shows up as an NVDA event unless the profile says they compete.
- `impact_for()`: the impact record of one security follows its own link relation (channel, exposure). Direction
  stays `unknown` (S2: direction needs disclosure and analysis, never a keyword guess).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sr.config import load
from sr.db import Conn
from sr.events.merge import Link
from sr.timeguard import ensure_utc


def profile_at(conn: Conn, company_id: str, as_of: datetime) -> dict[str, Any] | None:
    row = conn.execute(
        """select * from company_profile_versions where company_id = %s and effective_from <= %s
            order by version desc limit 1""",
        (company_id, ensure_utc(as_of, "as_of").to_pydatetime()),
    ).fetchone()
    return dict(row) if row else None


def read_through_links(conn: Conn, event_id: str, as_of: datetime) -> list[Link]:
    """Links for the related pilot companies of the event's direct subjects (written, idempotent)."""
    cfg = load("exposure")["read_through"]
    subj = conn.execute(
        """select l.security_id, s.company_id from event_security_links l join securities s using (security_id)
            where l.event_id = %s and l.relation in ('subject', 'acquirer', 'target')""",
        (event_id,),
    ).fetchall()
    linked = {
        r["security_id"]
        for r in conn.execute("select security_id from event_security_links where event_id = %s", (event_id,))
    }
    subj_cos = {r["company_id"]: r["security_id"] for r in subj}
    out: list[Link] = []
    for o in conn.execute(
        "select security_id, company_id from securities where coverage_tier = 'pilot' order by security_id"
    ).fetchall():
        if o["security_id"] in linked:
            continue
        prof = profile_at(conn, o["company_id"], as_of)
        rel = ((prof or {}).get("exposures") or {}).get("relations") or {}
        for prel, link_rel in cfg.items():
            hits = [c for c in rel.get(prel, []) if c in subj_cos]
            if hits:
                note = f"{prel}:{','.join(sorted(subj_cos[c] for c in hits))}"
                out.append(Link(o["security_id"], link_rel, note))
                break
    for lk in out:
        conn.execute(
            """insert into event_security_links (event_id, security_id, relation, exposure_note)
               values (%s, %s, %s::event_relation, %s) on conflict (event_id, security_id) do nothing""",
            (event_id, lk.security_id, lk.relation, lk.exposure_note),
        )
    return out


def impact_for(
    conn: Conn, event_id: str, security_id: str, facts: list[str], evidence_ids: list[str]
) -> list[dict[str, Any]]:
    cfg = load("exposure")
    link = conn.execute(
        "select relation, exposure_note from event_security_links where event_id = %s and security_id = %s",
        (event_id, security_id),
    ).fetchone()
    if link is None:
        return []
    ch = cfg["channels"][link["relation"]]
    exposure = ch["exposure"] or link["exposure_note"]
    if ch["exposure"] and link["exposure_note"] and link["relation"] not in ("subject",):
        exposure = f"{ch['exposure']}（{link['exposure_note']}）"
    return [
        {
            "fact": f,
            "exposure": exposure,
            "channel": ch["channel"],
            "relation": link["relation"],
            "direction": "unknown",
            "horizon": cfg["horizon_default"],
            "evidence_ids": sorted(evidence_ids),
        }
        for f in (facts or ["事件证据"])
    ]
