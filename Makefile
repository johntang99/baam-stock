# baam-stock developer commands (research only; no trade execution)
.PHONY: install gen seed fixture validate lint typecheck test db-replay db-reset check

DB_URL ?= postgresql://postgres:postgres@127.0.0.1:54322/postgres

install:
	pnpm install
	uv sync

gen:                      ## regenerate TS + pydantic from JSON Schemas
	pnpm --filter contracts gen:ts
	pnpm --filter contracts gen:py

seed:                     ## render supabase/seed/*.sql from config/*.yaml
	uv run python scripts/gen_seed.py

fixture:                  ## synthetic 1s fixture (虚构)
	uv run python scripts/make_fixture.py

validate: fixture
	uv run python scripts/validate_sample.py --fixture data/fixtures/nvda_2026-12-01_1s.parquet

lint:
	uv run ruff check .
	uv run ruff format --check .
	pnpm -r lint

typecheck:
	uv run mypy services/py/sr scripts
	pnpm -r typecheck

test:
	uv run python scripts/gen_seed.py --check
	uv run pytest services/py/tests -q   # set TEST_DATABASE_URL to include Postgres-backed tests
	pnpm --filter contracts test
	pnpm --filter web test

db-replay:                ## fresh DB: migrations + seeds + SQL assertions (needs psql and a running Postgres)
	scripts/db_replay.sh $(DB_URL)

db-reset:                 ## local Supabase (needs Docker)
	supabase db reset

check: lint typecheck test
	pnpm -r build
	cd apps/web && pnpm exec playwright test   # e2e on the build, fixture data (DP 2.15)
