"""Postgres access (psycopg 3). Connection string from DATABASE_URL (pooler) or an explicit URL; never logged."""

from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

Conn = psycopg.Connection[dict[str, Any]]


def connect(url: str | None = None, autocommit: bool = False) -> Conn:
    dsn = url or os.environ.get("DIRECT_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("no database URL: pass url or set DIRECT_URL / DATABASE_URL")
    return psycopg.connect(dsn, autocommit=autocommit, row_factory=dict_row)


def jsonb(value: Any) -> Jsonb:
    return Jsonb(value)


class ConflictStaleVersion(RuntimeError):
    """Optimistic lock lost (DC §9 CONFLICT_STALE_VERSION): re-read and decide, never overwrite."""
