# CHANGELOG

## Phase 0 — 2026-11-26

### Contract
- **contract-0.7.1** (patch on 0.7, see OPEN_QUESTIONS OQ-01/OQ-03): `securities.security_type` += `etf`, `index`;
  `primary_exchange` += `ARCX`, `XCBO`; `predictions.scenarios` (nullable jsonb).
- `packages/contracts`: 48 entity JSON Schemas (draft 2020-12) + `common.schema.json`; 30 are tabled (`x-tabled`).
  15 examples split from DC §8 (completed per OQ-05/06), all valid. Generated TS (`generated/index.ts`) and pydantic v2
  (`services/py/sr/contracts/_gen`).

### Database (`supabase/`)
- `migrations/0001_core.sql`: 30 tables, 57 enum types, FKs (cycle-safe), probability-sum / weight-sum / lock-field CHECKs,
  primary-scoring rule (D-23/D-48), immutability trigger on published predictions, append-only triggers (snapshots,
  collection items, reference quotes, training metrics, settlements), jobs queue, RLS enabled (no policies yet).
- Seeds generated from `config/*.yaml` by `scripts/gen_seed.py`: 18 securities (4 pilot, 2 batch2, 7 peer_only,
  5 reference), `bm_semis_peer_ex_<pilot>` v1 (11 equal weights) + `bm_soxx_ref`, industry templates, pilot profiles
  (semiconductor), targets td-0.2, schedule sched-0.1, XNYS trading sessions 2026–2027.
- `tests/0001_core_assertions.sql`: AC-01 + 17 expected rejections. `scripts/db_replay.sh` replays everything on a fresh DB.
- Applied to the Supabase project (`supabase db push --include-seed`, migration history recorded).

### Python (`services/py/sr`)
- `calendar`: XNYS session + overrides (D-04), `is_target_available` (D-18/D-28), `next_regular_session` (D-10),
  `schedule_slots` (D-43, half day / holiday / DST).
- `marketdata`: qr-0.1 rules (D-05/D-12), `find_first_sync_qualifying` (D-06/D-07), `MarketDataProvider` protocol,
  Parquet `FixtureProvider` with as_of guard.
- `benchmark.basket` (D-06/D-08), `labels.sigma` (sigma-0.1) + `labels.thresholds` (D-09), `eval.metrics`
  (Brier, BSS ×3 references, pinball), `eval.bootstrap` (day blocks, 2,000, fixed seed), `features` fs-0.2 (D-31).
- `timeguard.LookaheadError`: every time-dependent function refuses data after its as_of.
- 215 pytest cases; ruff + mypy --strict clean.

### Scripts, config, docs, infra
- `scripts/make_fixture.py` (SYNTHETIC NVDA + 11 peers + 5 reference symbols, 2026-12-01, wide spread / 3-min halt /
  stale quote / 2-constituent LULD), `scripts/validate_sample.py` (coverage, qualifying %, sync success % vs D-35).
- `config/`: decisions.yaml (D-01…D-48), quote_rules, sigma, targets, forecast_schedule, benchmarks, universe,
  calendar_overrides, industry_templates, data_sources, eval, features/fs-0.2.
- `docs/data_procurement.md` (all 拟选/未验证), `docs/OPEN_QUESTIONS.md`, this file.
- GitHub Actions CI (python, node, contracts-python-gen, migrations), local pre-commit hooks, Makefile, `.env.example`.
