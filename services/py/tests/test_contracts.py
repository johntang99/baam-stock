"""Contract integrity: schemas <-> examples <-> migration <-> seeds <-> decisions (single source of truth)."""

from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from sr.config import repo_root
from sr.eval.metrics import brier, pinball_by_quantile

ROOT = repo_root()
SCHEMAS = ROOT / "packages/contracts/schemas"
EXAMPLES = ROOT / "packages/contracts/examples"
MIGRATION = "\n".join(f.read_text() for f in sorted((ROOT / "supabase/migrations").glob("*.sql")))
SV = json.loads((SCHEMAS / "common.schema.json").read_text())["$defs"]["schema_version"]["const"]


def load_schemas() -> dict[str, dict[str, Any]]:
    return {
        p.name.replace(".schema.json", ""): json.loads(p.read_text()) for p in SCHEMAS.glob("*.schema.json")
    }


ALL = load_schemas()
COMMON = ALL["common"]
ENTITIES = {k: v for k, v in ALL.items() if k != "common"}
TABLED = sorted(k for k, v in ENTITIES.items() if v.get("x-tabled"))
REGISTRY = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in ALL.values()])


def validator(entity: str) -> Draft202012Validator:
    return Draft202012Validator(ENTITIES[entity], registry=REGISTRY, format_checker=FormatChecker())


def examples() -> list[Path]:
    return sorted(EXAMPLES.glob("*.json"))


# ---------------- schemas & examples ----------------
def test_schema_version_is_current() -> None:
    assert SV == "contract-0.7.3"
    import sr

    assert sr.SCHEMA_VERSION == SV


def test_all_schemas_are_valid_draft_2020_12() -> None:
    for s in ALL.values():
        Draft202012Validator.check_schema(s)
    assert len(ENTITIES) == 49 and len(TABLED) == 39  # 0.7.3: + model_versions


@pytest.mark.parametrize("path", examples(), ids=lambda p: p.name)
def test_example_validates(path: Path) -> None:
    entity = path.name.split(".")[0]
    doc = json.loads(path.read_text())
    errors = sorted(validator(entity).iter_errors(doc), key=str)
    assert not errors, "\n".join(e.message for e in errors)
    assert doc["schema_version"] == SV
    if doc.get("probabilities"):
        assert abs(sum(doc["probabilities"].values()) - 1) <= 1e-6


@pytest.mark.parametrize("path", examples(), ids=lambda p: p.name)
def test_example_roundtrips_through_pydantic(path: Path) -> None:
    entity = path.name.split(".")[0]
    mod = importlib.import_module(f"sr.contracts._gen.{entity}_schema")
    cls = next(
        v
        for k, v in vars(mod).items()
        if isinstance(v, type) and k.replace("_", "").lower() == entity.replace("_", "")
    )
    cls.model_validate(json.loads(path.read_text()))


def test_negative_examples_rejected() -> None:
    p = json.loads((EXAMPLES / "predictions.ex81_nvda_regular_60m.json").read_text())
    v = validator("predictions")
    assert not list(v.iter_errors(p))
    for mutate in (
        lambda d: d.update(status="won"),  # bad enum
        lambda d: d.update(published_at="2026-12-01 15:20:00"),  # not UTC ISO-8601 Z
        lambda d: d.update(surprise_field=1),  # unknown field
        lambda d: d["locked"].pop("sigma_hat_pp"),  # locked incomplete
        lambda d: d.pop("valid_until"),  # required (0.4)
    ):
        bad = json.loads(json.dumps(p))
        mutate(bad)
        assert list(v.iter_errors(bad)), f"mutation not rejected: {bad}"


def test_examples_agree_with_scoring_functions() -> None:
    p = json.loads((EXAMPLES / "predictions.ex81_nvda_regular_60m.json").read_text())
    s = json.loads((EXAMPLES / "prediction_settlements.ex81_nvda_regular_60m.json").read_text())
    assert brier(p["probabilities"], s["outcome_class"]) == pytest.approx(s["brier"], abs=1e-12)  # 0.5798
    lk = p["locked"]
    assert lk["threshold_pp"] == pytest.approx(lk["threshold_k"] * lk["sigma_hat_pp"])  # D-09
    assert s["relative_return_pp"] == pytest.approx(s["stock_return_pct"] - s["benchmark_return_pct"])
    m = json.loads((EXAMPLES / "predictions.ex81_nvda_regular_60m_move.json").read_text())
    ms = json.loads((EXAMPLES / "prediction_settlements.ex81_nvda_regular_60m_move.json").read_text())
    q = {k: v for k, v in m["move_quantiles"].items() if k != "unit"}
    for k, val in pinball_by_quantile(q, ms["abs_relative_move_pp"]).items():
        assert val == pytest.approx(ms["pinball_loss"][k], abs=1e-12)  # .035/.068/.053
    assert m["t0_quote_id"] == p["t0_quote_id"] and m["run_id"] == p["run_id"]  # shared quotes


def test_explanation_statements_cite_evidence() -> None:
    for path in EXAMPLES.glob("event_analysis_versions.*.json"):
        me = json.loads(path.read_text())["market_explanation"]
        for k in ("observed_facts", "possible_drivers", "counter_evidence"):
            for st in me[k]:
                assert st["evidence_ids"] or st["quote_ids"], f"{path.name}: uncited {k} (D-46)"


# ---------------- schema <-> migration ----------------
def _enums(sql: str) -> dict[str, list[str]]:
    out = {}
    for m in re.finditer(r"create type (\w+) as enum \((.*?)\);", sql, re.S):
        out[m.group(1)] = re.findall(r"'([^']*)'", m.group(2))
    return out


def _tables(sql: str) -> dict[str, dict[str, tuple[str, bool]]]:
    out: dict[str, dict[str, tuple[str, bool]]] = {}
    for m in re.finditer(r"create table (\w+) \((.*?)\n\);", sql, re.S):
        cols = {}
        for line in m.group(2).splitlines():
            line = line.strip()
            if (
                not line
                or line.startswith("--")
                or re.match(r"(primary key|unique|check|foreign key)\s*\(", line)
                or not re.match(r"[a-z_]\w* \w", line)
            ):
                continue
            name, typ = line.split()[0], line.split()[1].rstrip(",")
            cols[name] = (typ, " not null" in line or "primary key" in line)
        pk = re.search(r"primary key \(([^)]*)\)", m.group(2))
        if pk:
            for c in pk.group(1).split(","):
                cols[c.strip()] = (cols[c.strip()][0], True)
        out[m.group(1)] = cols
    return out


PG_ENUMS = _enums(MIGRATION)
PG_TABLES = _tables(MIGRATION)


def _resolve(node: dict[str, Any]) -> dict[str, Any]:
    if "anyOf" in node:
        node = next(x for x in node["anyOf"] if x.get("type") != "null")
    if "$ref" in node:
        name = node["$ref"].split("/")[-1]
        node = COMMON["$defs"][name]
    return node


def _schema_enum(node: dict[str, Any]) -> list[str] | None:
    n = _resolve(node)
    if n.get("type") == "array":
        n = _resolve(n["items"])
    return n.get("enum")


def test_tabled_entities_have_tables_and_schema_only_do_not() -> None:
    assert set(PG_TABLES) == set(TABLED)


@pytest.mark.parametrize("entity", TABLED)
def test_columns_match_schema(entity: str) -> None:
    props = set(ENTITIES[entity]["properties"]) - {"schema_version"}
    assert set(PG_TABLES[entity]) == props, (
        f"only in SQL: {set(PG_TABLES[entity]) - props}; only in schema: {props - set(PG_TABLES[entity])}"
    )


@pytest.mark.parametrize("entity", TABLED)
def test_enum_values_match_schema(entity: str) -> None:
    for col, node in ENTITIES[entity]["properties"].items():
        if col == "schema_version":
            continue
        values = _schema_enum(node)
        pgtype = PG_TABLES[entity][col][0].removesuffix("[]")
        if values is None:
            assert pgtype not in PG_ENUMS, f"{entity}.{col}: SQL enum {pgtype} but schema has no enum"
            continue
        assert pgtype in PG_ENUMS, f"{entity}.{col}: schema enum but SQL type {pgtype}"
        assert PG_ENUMS[pgtype] == values, f"{entity}.{col}: {PG_ENUMS[pgtype]} != {values}"


@pytest.mark.parametrize("entity", TABLED)
def test_required_matches_not_null(entity: str) -> None:
    required = set(ENTITIES[entity]["required"])
    not_null = {c for c, (_, nn) in PG_TABLES[entity].items() if nn}
    assert required == not_null, f"required-only: {required - not_null}; not-null-only: {not_null - required}"


# ---------------- seeds, config, decisions ----------------
def test_seed_files_up_to_date() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gen_seed.py"), "--check"], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr


def test_decisions_mirror_complete() -> None:
    d = yaml.safe_load((ROOT / "config/decisions.yaml").read_text())
    ids = [x["id"] for x in d["decisions"]]
    assert ids == [f"D-{i:02d}" for i in range(1, 49)]
    for x in d["decisions"]:
        assert set(x["status"]) <= {"proposed", "from_spec", "to_verify", "confirmed"}, x["id"]
    for i in range(5, 13):
        assert d["decisions"][i - 1]["status"] == ["confirmed"], f"D-{i:02d} confirmed 2026-11-26"
    by = {x["id"]: x for x in d["decisions"]}
    assert by["D-09"]["params"].get("k") == 0.25 or "0.25" in json.dumps(by["D-09"]["params"])


def test_config_values_match_decisions() -> None:
    from sr.config import load

    qr = load("quote_rules")
    assert qr["sync"]["tolerance_ms"] == 2000 and qr["sync"]["settle_tolerance_s"] == 30  # D-06, D-07
    assert qr["qualifying"]["max_spread_bp"] == 20 and qr["qualifying"]["max_quote_age_s"] == 5  # D-12
    assert load("sigma")["threshold_k"] == 0.25 and load("sigma")["ewma_half_life_days"] == 10  # D-09
    assert len(load("benchmarks")["semis_peer_v1"]["constituents"]) == 12  # D-08
