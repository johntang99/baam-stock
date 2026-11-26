"""Shared test fixtures. All market data here is SYNTHETIC (虚构)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
import pytest

from sr.calendar.calendar import ET
from sr.config import repo_root

FIXTURE = repo_root() / "data" / "fixtures" / "nvda_2026-12-01_1s.parquet"
PEERS_EX_NVDA = ["AMD", "AVGO", "MU", "QCOM", "TXN", "INTC", "ADI", "MRVL", "AMAT", "LRCX", "KLAC"]


def et(d: date, hhmmss: str) -> datetime:
    """America/New_York wall clock -> aware datetime (tests use ET inputs, converted explicitly)."""
    parts = [int(x) for x in hhmmss.split(":")]
    while len(parts) < 3:
        parts.append(0)
    return datetime.combine(d, time(*parts), tzinfo=ET)


def _load_script(name: str):  # type: ignore[no-untyped-def]
    path = repo_root() / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def fixture_path() -> Path:
    """The synthetic 1s fixture; generated deterministically if missing (data/ is gitignored)."""
    if not FIXTURE.exists():
        mf = _load_script("make_fixture")
        df, meta = mf.build(20261201)
        import json

        import pyarrow as pa
        import pyarrow.parquet as pq

        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        t = pa.Table.from_pandas(df, preserve_index=False)
        t = t.replace_schema_metadata(
            {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in meta.items()}
        )
        pq.write_table(t, FIXTURE, compression="zstd")
    return FIXTURE


@pytest.fixture(scope="session")
def raw_quotes(fixture_path: Path) -> pd.DataFrame:
    return pd.read_parquet(fixture_path)


@pytest.fixture(scope="session")
def evaluated(raw_quotes: pd.DataFrame) -> pd.DataFrame:
    from sr.marketdata.quote_rules import evaluate_quotes

    return evaluate_quotes(raw_quotes)


@pytest.fixture(scope="session")
def basket_ex_nvda() -> list[str]:
    return ["sec_" + p.lower() for p in PEERS_EX_NVDA]


@pytest.fixture
def load_script():  # type: ignore[no-untyped-def]
    return _load_script


# ---------------------------------------------------------------- Postgres-backed tests
# TEST_DATABASE_URL = admin URL of a throwaway Postgres (CI service / local). A template database with all
# migrations + seeds is built once per session; each test gets a fresh copy (CREATE DATABASE … TEMPLATE).
import os  # noqa: E402
import uuid  # noqa: E402
from collections.abc import Iterator  # noqa: E402

EVIDENCE_ARCHIVE = Path(__file__).parent / "fixtures" / "evidence"


def _admin_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


def _swap_db(url: str, name: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{name}"


@pytest.fixture(scope="session")
def pg_template() -> Iterator[str]:
    admin = _admin_url()
    if not admin:
        pytest.skip("TEST_DATABASE_URL not set (Postgres-backed tests)")
    import psycopg

    name = f"sr_tmpl_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f"create database {name}")
    url = _swap_db(admin, name)
    root = repo_root()
    with psycopg.connect(url, autocommit=True) as c:
        for f in sorted((root / "supabase/migrations").glob("*.sql")) + sorted(
            (root / "supabase/seed").glob("*.sql")
        ):
            c.execute(f.read_text())
    yield name
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f"drop database if exists {name} with (force)")


@pytest.fixture
def db_url(pg_template: str) -> Iterator[str]:
    import psycopg

    admin = _admin_url()
    assert admin
    name = f"sr_t_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f"create database {name} template {pg_template}")
    yield _swap_db(admin, name)
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f"drop database if exists {name} with (force)")


@pytest.fixture
def conn(db_url: str):  # type: ignore[no-untyped-def]
    from sr.db import connect

    c = connect(db_url, autocommit=True)
    yield c
    c.close()


@pytest.fixture
def doc_storage(tmp_path: Path):  # type: ignore[no-untyped-def]
    from sr.evidence.storage import LocalDocStorage

    return LocalDocStorage(tmp_path / "evidence")
