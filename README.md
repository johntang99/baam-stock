# baam-stock

US-stock short-term research and forecast system: first NVDA, AMD, AVGO and MU, then TSM and MRVL.
It is for **research and validation only**. It does not execute trades and is not investment advice.
All sample data in this repository is **synthetic (虚构)**.

**Status:** Phase 0 is done (contracts, database, calendar, quote rules, scoring, features). Phase 1 starts after the
decision table and data vendors are confirmed (see `docs/OPEN_QUESTIONS.md`).

| Path | What |
|---|---|
| `docs/` | Design: `BUILDING_MASTER_PLAN.md` (MP), `DATA_CONTRACT.md` (DC, contract-0.7.1), `DEVELOPMENT_PHASES.md` (DP), plus CHANGELOG, OPEN_QUESTIONS, data_procurement |
| `packages/contracts/` | JSON Schemas (single source of truth), examples, generated TS types |
| `services/py/sr/` | Python services (uv): calendar, marketdata, benchmark, labels, eval, features |
| `supabase/` | migrations, generated seeds, SQL assertions |
| `config/` | Versioned parameters (decision-table defaults); `decisions.yaml` mirrors MP §9 |
| `scripts/` | seed generator, synthetic fixture, sample validation, DB replay |
| `apps/web/` | Next.js shell (pages start in Phase 2) |
| `prototype/` | Clickable HTML mock (reference only) |

## Quick start
```bash
pnpm install && uv sync
make check                                   # lint, mypy, pytest, contract examples, build
make validate                                # synthetic fixture + availability report
scripts/db_replay.sh "$DATABASE_URL_ADMIN"   # migrations + seeds + SQL assertions on a fresh database
```
Secrets live only in `.env.local` (gitignored); see `.env.example` for the variable names.
