"""Ingest raw documents into versioned evidence (DP 1.04; DC §3.2, §7).

- source_documents keyed by (source_id, external_ref); one row per logical document.
- source_document_versions append-only; the same normalised content again => duplicate (no new version,
  no analysis job: AC-07). Different content for the same document => new version marked is_correction_of.
- Four timestamps: source_published_at (+precision or missing_reason), received_at, available_at (processing
  done; archived documents keep their recorded value), simulated_available_at for simulated replays (AC-06).
- Restricted screen => visibility=restricted_review and no analysis job (AC-25).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sr.config import load
from sr.db import Conn, jsonb
from sr.evidence.hashing import content_hash, normalized_text
from sr.evidence.screening import screen
from sr.evidence.sources.base import RawDocument
from sr.evidence.storage import LocalDocStorage
from sr.ids import new_id
from sr.timeguard import ensure_utc

Status = Literal["new", "correction", "duplicate"]


@dataclass(frozen=True)
class IngestResult:
    status: Status
    doc_id: str
    doc_version_id: str
    version: int
    visibility: str
    job_id: str | None
    screen_reasons: tuple[str, ...] = ()


def _validate(raw: RawDocument) -> None:
    if raw.source_published_at is None and not raw.missing_reason:
        raise ValueError(
            f"{raw.external_ref}: source_published_at missing without missing_reason (DC §1, AC-06)"
        )
    if raw.source_published_at is not None and not raw.source_published_precision:
        raise ValueError(f"{raw.external_ref}: source_published_precision required with source_published_at")
    if (raw.arrival_mode == "simulated") != (raw.simulated_available_at is not None):
        raise ValueError(f"{raw.external_ref}: simulated_available_at iff arrival_mode=simulated")
    if raw.arrival_mode == "archived" and raw.available_at is None:
        raise ValueError(f"{raw.external_ref}: archived documents need their recorded available_at")


def ingest(
    conn: Conn, raw: RawDocument, now: datetime | None = None, storage: LocalDocStorage | None = None
) -> IngestResult:
    """Idempotent; runs in its own transaction. `now` = when parsing/verification finished (available_at)."""
    _validate(raw)
    cfg = load("evidence")
    processed = ensure_utc(now or datetime.now(UTC), "now").to_pydatetime()
    received = ensure_utc(raw.received_at, "received_at").to_pydatetime()
    available = (
        ensure_utc(raw.available_at, "available_at").to_pydatetime()
        if raw.available_at
        else max(processed, received)
    )
    h = content_hash(raw.content, raw.content_type, cfg["hash"]["normalize_whitespace"])
    storage = storage or LocalDocStorage()

    with conn.transaction():
        src = conn.execute(
            "select license_scope from data_sources where source_id = %s", (raw.source_id,)
        ).fetchone()
        if src is None:
            raise ValueError(f"unknown source_id {raw.source_id}")
        conn.execute(
            """insert into source_documents (doc_id, source_id, canonical_url, external_ref, origin_doc_id, subject_company_ids)
               values (%s, %s, %s, %s, %s, %s) on conflict (source_id, external_ref) do nothing""",
            (
                new_id("doc"),
                raw.source_id,
                raw.canonical_url,
                raw.external_ref,
                raw.origin_doc_id,
                list(raw.subject_company_ids),
            ),
        )
        doc = conn.execute(
            "select doc_id from source_documents where source_id = %s and external_ref = %s for update",
            (raw.source_id, raw.external_ref),
        ).fetchone()
        assert doc is not None
        doc_id = doc["doc_id"]

        dup = conn.execute(
            "select doc_version_id, version, visibility from source_document_versions where doc_id = %s and content_hash = %s",
            (doc_id, h),
        ).fetchone()
        if dup is not None:
            return IngestResult(
                "duplicate", doc_id, dup["doc_version_id"], dup["version"], dup["visibility"], None
            )

        prev = conn.execute(
            "select doc_version_id, version from source_document_versions where doc_id = %s order by version desc limit 1",
            (doc_id,),
        ).fetchone()
        version = (prev["version"] + 1) if prev else 1
        sr_ = screen(f"{raw.title}\n{normalized_text(raw.content, raw.content_type)}", src["license_scope"])
        store_allowed = src["license_scope"] in ("public", "licensed_internal")
        path = (
            storage.put(raw.source_id, doc_id, version, raw.content, raw.content_type)
            if store_allowed
            else None
        )
        dv_id = new_id("docv")
        conn.execute(
            """insert into source_document_versions (doc_version_id, doc_id, version, content_hash, storage_path, locator,
                 source_published_at, source_published_precision, missing_reason, received_at, available_at,
                 arrival_mode, simulated_available_at, is_correction_of, visibility)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                dv_id,
                doc_id,
                version,
                h,
                path,
                raw.locator,
                raw.source_published_at,
                raw.source_published_precision,
                raw.missing_reason,
                received,
                available,
                raw.arrival_mode,
                raw.simulated_available_at,
                prev["doc_version_id"] if prev else None,
                sr_.visibility,
            ),
        )
        job_id = None
        if sr_.visibility != "restricted_review":
            aj = cfg["analysis_job"]
            job_id = new_id("job")
            conn.execute(
                """insert into jobs (job_id, job_type, payload, idempotency_key, run_after)
                   values (%s, %s, %s, %s, %s) on conflict (idempotency_key) do nothing""",
                (
                    job_id,
                    aj["job_type"],
                    jsonb({"doc_version_id": dv_id, "doc_id": doc_id}),
                    aj["idempotency_prefix"] + dv_id,
                    available,
                ),
            )
        return IngestResult(
            "correction" if prev else "new", doc_id, dv_id, version, sr_.visibility, job_id, sr_.reasons
        )


def ingest_all(
    conn: Conn, docs: list[RawDocument], now: datetime | None = None, storage: LocalDocStorage | None = None
) -> list[IngestResult]:
    return [ingest(conn, d, now, storage) for d in docs]
