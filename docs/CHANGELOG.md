# CHANGELOG

## Phase 1 · 1.18 corpus + Claude draft trial — 2026-11-26
- Corpus: 291 public SEC documents (NVDA, AMD, AVGO, MU, TSM, MRVL; 111 EX-99 exhibits, 180 filing texts).
  Exhibits found by declared document type from the filing index.
- extract-0.3 (OQ-38): metric/unit enums, `metric_label`, `segment`; 8 more canonical metrics; table-row
  scale markers; company period labels ("third quarter of 2026" -> FY2026Q3, "fiscal 2026" -> FY2026);
  growth rates may exceed 100%; normalised values rounded.
- Claude draft trial on 20 stratified documents (22 calls incl. 3 on the first doc, ~$2 at list price, all
  logged to `llm_calls`): 103 verified draft facts; candidates + drop reasons saved for reviewers.
  `prelabel_extraction.py`: `--replace-drafts`, `--sample stratified`, `--keys/--exclude`, `--log-db`,
  `--recheck` (rebuild drafts from saved candidates, no API calls), cost summary.
- Labelling guide: review focus from the trial (multi-column table periods, GAAP/non-GAAP columns, NT$ figures).
- OQ-37, OQ-38 confirmed by user. Tests: 326 (33 Postgres-backed).

## Phase 1 · 1.18 extraction evaluation set (tooling) — 2026-11-26
- Prompt extract-0.2: facts also carry `direction`, `scope`, `certainty` (D-32 field groups).
- `scripts/fetch_sec_corpus.py` (CIKs from SEC company_tickers.json, 8-K/6-K press-release exhibits + primary
  documents, manifest with raw/text hashes; live mode needs `SEC_EDGAR_USER_AGENT`), `scripts/prelabel_extraction.py`
  (drafts only; paid provider requires `--allow-spend`), `scripts/run_extraction_eval.py`.
- `sr.llm.labels` (gold label model), `sr.llm.eval_extraction` (matching, four field groups, extraction_eval_runs),
  `sr.features.llm_gate` (`require_approved`, `event_feature_inputs`: facts from unapproved prompts are refused, AC-30).
- `docs/labeling/extraction-v0.md` labelling guide; `/data/labels/` committed, raw corpus stays local.
- OPEN_QUESTIONS OQ-36 confirmed, OQ-37 new. Tests: 320 (33 Postgres-backed).

## Phase 1 · 1.22 historical analogues — 2026-11-26
- `sr.events.analogues` (hc-0.1, `config/analogues/hc-0.1.yaml`): past-only cases (available and settled by
  as_of), no self-match within an event chain, match keys event_type + subtype + industry_template +
  market_state (+ surprise bucket for earnings), min 8 cases with relaxation drop_subtype -> peer_group ->
  sector_wide, then `insufficient` with no statistics; median / IQR / share > 0, n, period, sorted case_ids
  (AC-38). `load_cases` builds the point-in-time case library from published analysis versions.
- OPEN_QUESTIONS OQ-36. Tests: 313 (32 Postgres-backed).

## Phase 1 · group 3 (DP 1.27–1.28) — 2026-11-26
- 1.27 `sr.evidence.collection_log.run_collection`: one `collection_items` row per retrieved item (kept, duplicate
  -> original, excluded_irrelevant, excluded_after_asof, excluded_restricted with placeholder only, pending_review,
  fetch_failed); per-source poll status; market data as one summary item; counts and channel x category matrix
  computed from the items; replaying the same window gives the same item set (AC-56).
  `sr.evidence.classify` (rules: channel incl. peer_company, category, relevance, mentions).
  Sources report per-document fetch failures (`FetchFailure`).
- 1.28 `sr.events.citations` (every observed fact / driver / counter statement must cite existing evidence or
  quotes, optionally scoped to the run; otherwise moved to unexplained) and `sr.events.reasoning.build`
  (deterministic market_fact / evidence_fact / timing_check / gap / conclusion steps; LLM-drafted statements are
  citation-checked first; drivers whose evidence is not provably earlier than the move become concurrent events,
  AC-10/AC-57).
- Migration `0003_collection_links.sql`: collection items immutable except links (OQ-34). Earnings and policy
  pipelines now link their collection items to the event.
- Tests: 304 (31 Postgres-backed). OPEN_QUESTIONS OQ-32..35 (defaults confirmed by user 2026-11-26).

## Phase 1 · group 2 (DP 1.07–1.08) — 2026-11-26
- 1.07 earnings: `sr.events.factcheck` (canonical metrics, GAAP/non-GAAP EPS as separate fields, value must be
  printed in its own quote with the right scale, unit normalisation, conflict withholding),
  `sr.events.expectations` (pre-disclosure consensus only; day-precision snapshots must be dated earlier;
  basis must match; AC-09 `no_pre_event_consensus`), `sr.events.earnings` (extract -> check -> event/evidence ->
  comparison -> flash analysis with cited observed facts; market reaction pending D-13).
- 1.08 policy: `FederalRegisterSource` (FR API, date precision), `sr.events.policy` (BIS template: identity
  `policy:BIS:<doc>`, official evidence, milestones by document type, topic -> exposure links, progress
  `effective`, per-security flash analyses with market-baseline-only hand-off).
- `sr.events.readiness` (AC-12 rule from `config/readiness.yaml`), idempotent `ensure_milestone`,
  forward-only `set_progress_status`; configs `earnings.yaml`, `policy_templates.yaml`, `readiness.yaml`.
- Tests: 295 (25 Postgres-backed). OPEN_QUESTIONS OQ-28..31 (defaults confirmed by user 2026-11-26).

## Phase 1 · group 1 (DP 1.03–1.06) — 2026-11-26
- **contract-0.7.2** (OQ-23, approved by user 2026-11-26): evidence/event entities tabled; new `llm_calls`; DC §3.4b.
- `supabase/migrations/0002_evidence_events.sql`: 8 tables, 12 enums, append-only guards (document versions:
  only `visibility` may change; evidence: only `visibility`/`verification_status`; analysis versions and LLM calls
  immutable), events optimistic-lock trigger (row_version +1 only, current pointer never backwards),
  null-reason CHECK for missing publish times (AC-06), view `event_analysis_current`, RLS on.
- `sr.evidence`: `EvidenceSource` protocol; SEC EDGAR (submissions → primary documents) and IR RSS/Atom
  adapters; archive + rate-limited live transports (live needs `SEC_EDGAR_USER_AGENT`); whitespace-insensitive
  content hashing; MNPI screen; local raw store; `ingest` (versions, corrections, duplicates, `analyze_event`
  jobs); `PointInTimeReader` (raises on look-ahead).
- `sr.llm`: provider protocol, fake provider, Claude provider (`claude-opus-5-5`, structured output, no tools,
  refusal fallback); every fact must quote the source verbatim or the call is rejected; calls logged.
- `sr.events`: identity keys, `attach_evidence` (independent-origin counting, derived evidence status),
  milestones, `publish_analysis` with optimistic lock (AC-08).
- Tests: 276 (19 Postgres-backed via `TEST_DATABASE_URL`, run in CI against postgres:17). Synthetic archive in
  `services/py/tests/fixtures/evidence/`. `.gitignore` `data/` anchored to the repo root.

## 2026-11-26 — decisions confirmed
- contract-0.7.1 approved (OQ-01).
- D-05…D-12 confirmed with their default values; status `confirmed` added to the decision-table vocabulary (MP §9, `config/decisions.yaml`). No parameter values changed.
- OQ-03, OQ-10 defaults confirmed. OQ-08 resolved: no backdated basket versions; historical training labels apply `semis_peer_v1` retroactively and record it in `training_dataset_versions.source_versions` (Phase 1 dataset builder must do this).

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
