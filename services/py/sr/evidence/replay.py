"""Point-in-time evidence reads (DC §1.1 回放规则, §4): at time T only versions whose effective availability
(simulated_available_at for simulated arrivals, else available_at) is <= T exist. Asking for anything later
raises LookaheadError. Restricted-review material is excluded unless explicitly requested (admin only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sr.db import Conn
from sr.timeguard import LookaheadError, ensure_utc

_EFFECTIVE = "coalesce(v.simulated_available_at, v.available_at)"


class PointInTimeReader:
    def __init__(self, conn: Conn, as_of: datetime, include_restricted: bool = False) -> None:
        self.conn = conn
        self.as_of = ensure_utc(as_of, "as_of").to_pydatetime()
        self.include_restricted = include_restricted

    def _check(self, row: dict[str, Any]) -> dict[str, Any]:
        eff = row["simulated_available_at"] or row["available_at"]
        if eff > self.as_of:
            raise LookaheadError(
                f"{row['doc_version_id']} available {eff.isoformat()} > as_of {self.as_of.isoformat()}"
            )
        if row["visibility"] == "restricted_review" and not self.include_restricted:
            raise PermissionError(f"{row['doc_version_id']} is under restricted review")
        return row

    def versions(self, company_id: str | None = None) -> list[dict[str, Any]]:
        """Latest version of each document as known at as_of (corrections after as_of are invisible)."""
        rows = self.conn.execute(
            f"""select distinct on (v.doc_id) v.*, d.source_id, d.external_ref, d.subject_company_ids
                from source_document_versions v join source_documents d using (doc_id)
                where {_EFFECTIVE} <= %(t)s
                  and (%(restricted)s or v.visibility <> 'restricted_review')
                  and (%(co)s::text is null or %(co)s = any(d.subject_company_ids))
                order by v.doc_id, v.version desc""",
            {"t": self.as_of, "restricted": self.include_restricted, "co": company_id},
        ).fetchall()
        return [self._check(r) for r in rows]  # defence in depth: the filter above must already hold

    def version(self, doc_version_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "select * from source_document_versions where doc_version_id = %s", (doc_version_id,)
        ).fetchone()
        if row is None:
            raise KeyError(doc_version_id)
        return self._check(row)
