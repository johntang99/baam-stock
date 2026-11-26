"""Attach evidence to events (S2§3.2): get-or-create by identity_key, idempotent evidence insert, independent
source counting via independent_origin_key, evidence_status derived from all non-retracted evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sr.db import ConflictStaleVersion, Conn, jsonb
from sr.events.identity import validate
from sr.ids import new_id
from sr.timeguard import ensure_utc

_RANK = {"pending": 0, "media_report": 1, "primary_confirmed": 2}


@dataclass(frozen=True)
class EvidenceIn:
    doc_version_id: str
    claim: str
    span: dict[str, Any]
    verification_status: str  # pending | media_report | primary_confirmed | conflicting | retracted
    independent_origin_key: str  # same for re-publications of one original
    claimant: str | None = None


@dataclass(frozen=True)
class Link:
    security_id: str
    relation: str
    exposure_note: str | None = None


@dataclass(frozen=True)
class MergeResult:
    event_id: str
    created: bool
    evidence_id: str
    evidence_created: bool
    evidence_status: str
    n_independent_origins: int
    row_version: int


def derive_evidence_status(statuses: list[str]) -> str:
    live = [s for s in statuses if s != "retracted"]
    if not live:
        return "retracted" if statuses else "pending"
    if "conflicting" in live:
        return "conflicting"
    return max(live, key=lambda s: _RANK[s])


def attach_evidence(
    conn: Conn,
    identity_key: str,
    category: str,
    evidence: EvidenceIn,
    links: list[Link] | None = None,
    subtype: str | None = None,
    now: datetime | None = None,
) -> MergeResult:
    validate(identity_key)
    t = ensure_utc(now or datetime.now(UTC), "now").to_pydatetime()
    with conn.transaction():
        dv = conn.execute(
            "select available_at, simulated_available_at, visibility from source_document_versions where doc_version_id = %s",
            (evidence.doc_version_id,),
        ).fetchone()
        if dv is None:
            raise KeyError(f"unknown doc_version_id {evidence.doc_version_id}")
        created = (
            conn.execute(
                """insert into events (event_id, category, subtype, identity_key, first_seen_at)
               values (%s, %s, %s, %s, %s) on conflict (identity_key) do nothing returning event_id""",
                (new_id("evt"), category, subtype, identity_key, t),
            ).fetchone()
            is not None
        )
        ev = conn.execute("select * from events where identity_key = %s", (identity_key,)).fetchone()
        assert ev is not None
        if ev["category"] != category:
            raise ValueError(
                f"{identity_key}: category {category} != existing {ev['category']} (needs review)"
            )

        evd = conn.execute(
            """insert into event_evidence (evidence_id, event_id, doc_version_id, claim, claimant, span,
                 verification_status, available_at, visibility, independent_origin_key)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (event_id, doc_version_id, claim) do nothing returning evidence_id""",
            (
                new_id("evd"),
                ev["event_id"],
                evidence.doc_version_id,
                evidence.claim,
                evidence.claimant,
                jsonb(evidence.span),
                evidence.verification_status,
                dv["simulated_available_at"] or dv["available_at"],
                dv["visibility"],
                evidence.independent_origin_key,
            ),
        ).fetchone()
        evidence_created = evd is not None
        if evd is None:
            evd = conn.execute(
                "select evidence_id from event_evidence where event_id = %s and doc_version_id = %s and claim = %s",
                (ev["event_id"], evidence.doc_version_id, evidence.claim),
            ).fetchone()
        assert evd is not None

        for lk in links or []:
            conn.execute(
                """insert into event_security_links (event_id, security_id, relation, exposure_note)
                   values (%s,%s,%s,%s) on conflict (event_id, security_id) do nothing""",
                (ev["event_id"], lk.security_id, lk.relation, lk.exposure_note),
            )

        rows = conn.execute(
            "select verification_status, independent_origin_key from event_evidence where event_id = %s",
            (ev["event_id"],),
        ).fetchall()
        status = derive_evidence_status([r["verification_status"] for r in rows])
        n_origins = len(
            {r["independent_origin_key"] for r in rows if r["verification_status"] != "retracted"}
        )
        row_version = ev["row_version"]
        if status != ev["evidence_status"]:
            upd = conn.execute(
                """update events set evidence_status = %s, row_version = row_version + 1
                   where event_id = %s and row_version = %s returning row_version""",
                (status, ev["event_id"], ev["row_version"]),
            ).fetchone()
            if upd is None:
                raise ConflictStaleVersion(f"event {ev['event_id']} changed concurrently; retry")
            row_version = upd["row_version"]
        return MergeResult(
            ev["event_id"], created, evd["evidence_id"], evidence_created, status, n_origins, row_version
        )


_PROGRESS = {
    "pending": {"outcome_confirmed", "effective", "terminated"},
    "outcome_confirmed": {"effective", "terminated"},
    "effective": {"terminated"},
    "terminated": set(),
}


def set_progress_status(conn: Conn, event_id: str, status: str) -> int:
    """Forward-only progress transition under the optimistic lock; returns the new row_version (no-op if equal)."""
    ev = conn.execute(
        "select progress_status, row_version from events where event_id = %s", (event_id,)
    ).fetchone()
    if ev is None:
        raise KeyError(event_id)
    if ev["progress_status"] == status:
        return int(ev["row_version"])
    if status not in _PROGRESS[ev["progress_status"]]:
        raise ValueError(f"event {event_id}: {ev['progress_status']} -> {status} not allowed")
    upd = conn.execute(
        "update events set progress_status = %s, row_version = row_version + 1 where event_id = %s and row_version = %s "
        "returning row_version",
        (status, event_id, ev["row_version"]),
    ).fetchone()
    if upd is None:
        raise ConflictStaleVersion(f"event {event_id} changed concurrently; retry")
    return int(upd["row_version"])
