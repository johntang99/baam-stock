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
