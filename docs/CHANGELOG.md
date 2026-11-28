# CHANGELOG

## Phase 1 · 1.25 scenario tests: after-hours +8 %, after-hours basket missing, rumour -> confirmation (AC-39..41) — 2026-11-28
- `sr/snapshot/triggers.py`: `detect_market_move` (rule `move_abs_v1`: |move| >= 3 % vs the regular close outside
  regular hours, vs 15 minutes earlier inside them) -> a `market_move` snapshot trigger.
- `sr/calendar/windows.next_session_start_bound`: next-session windows start no earlier than 09:31 ET (D-10).
- Snapshot summary outside regular hours without a basket: "盘后基准不可计算，仅显示绝对涨跌" (AC-40).
- `publish_explanation`: media-report evidence on an event not yet primary-confirmed adds "未经证实：…" to
  `unexplained` and the `unconfirmed_evidence` data gap; dropped once confirmed (AC-41). Fixes: the first analysis
  of an event published here now gets `analysis_kind = flash` and a default event-outcome readiness.
- `services/py/tests/scenarios/test_after_hours_move.py`, `test_rumor_to_confirm.py` (DP names prefixed `test_`
  for pytest): 16:20 ET earnings + post-market +8 % -> market_move post-market snapshot with the analysis, no
  regular_60m published, next-session start 09:31; basket missing after hours -> relative null, wording shown;
  rumour -> v1 未经证实, 8-K -> v2 supersedes v1, evidence primary_confirmed, v1 unchanged.
- OQ-55 adopted (routine). Tests: 5 new.

## Phase 1 · 1.24 valuation background, explanation only (AC-42) — 2026-11-28
- `sr/events/valuation.py` (val-0.1, `config/valuation.yaml`): `valuation_context` gives `{as_of, fwd_pe,
  fwd_pe_pctile_3y, peer_median_fwd_pe, ev_sales_ntm?, source_id, note}` from values available by the analysis
  time (3-year percentile needs >= 60 values; peer median needs >= 3 peers no older than 7 days); peers from
  `company_profile_versions.valuation_peers`, else the benchmark basket. `NoValuationSource` (the default until
  D-16) gives no context, so the key is absent and the row is hidden. `publish_explanation(valuation=…)` puts it
  into `market_explanation`.
- AC-42 guard: `check_feature_inputs` raises `ExplanationOnlyField` for valuation fields in the model design
  matrix, the publish-time feature row and `event_feature_inputs`.
- OQ-54 adopted (routine). Tests: 10 new.

## Phase 1 · 1.23 run state, source issues, display_state view (AC-49 Phase 1 part) — 2026-11-28
- `sr/snapshot/quality.py` (quality-0.2): the snapshot quality / run-state rules moved out of the builder;
  per-source problems from the collection run (`timeout` / `error`, or latency > 60 s) become `quality_issues`
  in the DC shape and make the snapshot `partial` / `degraded`.
- Migration `0005_validity_views.sql`: `prediction_display_state_at(t)` (settled > superseded with the newer id >
  expired > current, only predictions published by t) and view `prediction_display_state`;
  `security_snapshot_current_at(t)` (latest snapshot per security by t, `expired`) and view
  `security_snapshot_current`. Views are `security_invoker`, so table RLS applies through them.
- OQ-53 adopted (routine). Tests: 8 new (source issues, assess order, degraded snapshot, last_valid_at,
  snapshot expiry and point-in-time, the four display states, abstained expiry, security_invoker).

## Phase 1 · 1.19 minimal read-only replay page — 2026-11-28
- `apps/web/app/(market)/replay/page.tsx` (list) and `apps/web/app/(market)/replay/[prediction_id]/page.tsx`
  (one prediction: forecast, snapshot, 12 locked fields, model, t0 / end quotes, settlement and reason, checks),
  server-rendered at request time from the JSON reports `sr replay` now writes to `data/replay/reports/`
  (`write_json_reports`, `synthetic` flag from the provider). `apps/web/lib/replay.ts` validates prediction ids and
  keeps reads inside the report directory. Home page links to it; its scope note now follows CLAUDE.md
  (internal team only, not investment advice).
- Web tests: `pnpm --filter web test` (Node's test runner, `--experimental-strip-types`); added to `make check`
  and CI, whose node job moves to Node 22. Verified by building the app and fetching the pages for 8 synthetic
  reports (all fields shown; unknown / traversal ids return 404). OQ-52 adopted (routine).

## Phase 1 · 1.17 day replay + line-by-line verification report — 2026-11-28
- `sr/replay/runner.py`: `replay_day` runs the pipeline at each scheduled sched-0.1 intraday slot (replay mode,
  provider limited to the slot time, primary slot samples), settles every published prediction after the close
  with the quotes received by then, and writes `data/replay/<security>_<date>.md` + `.html`.
- `sr/replay/report.py`: `prediction_report` lists the snapshot, locked versions, model + feature row, t0 / end
  quotes, returns, class or move, Brier / pinball and settlement reason, and runs automatic checks (locked keys,
  published before t0, inputs not after publication, end quote at/after the target time, one reporting
  settlement, hit consistent); Markdown + escaped HTML; a day summary table.
- CLI: `sr replay --security --date --fixture` and `sr report --prediction`; shared model / history defaults.
- OQ-51 adopted (routine). Tests: 6 new (8 slot predictions settled, all checks pass, acceptance fields present,
  move / abstained reports, inert HTML, a t0 before publication is flagged).

## Phase 1 · 1.16 one-click pipeline + `sr run` CLI (AC-34 Phase 1 part) — 2026-11-28
- `sr/pipeline/orchestrator.py`: `run_pipeline` writes `pipeline_runs` + 8 `pipeline_run_steps` per security
  (collect -> verify -> analyse -> snapshot -> readiness -> infer -> publish -> schedule settlement) with statuses,
  attempts, details and errors; modes `replay` (point-in-time provider) and `dry_run` (savepoint rolled back, only
  the report rows kept); reuse when inputs are unchanged (`outputs.reused`), `force_recompute` -> separate
  `on_demand` forecasts; resume of a failed run from its first unfinished step; settlement scheduled as
  `settle_due` jobs. `sr run --mode replay|dry_run` in `sr/cli.py`.
- Fix found by the replay guard: inference read market data at the publish time (600 ms after the snapshot);
  features, sigma and HAR history now read at the snapshot's `analysis_as_of` (OQ-48 updated).
- `forecast_snapshot` gains `publish_now` (dry run) and `force_recompute_tag`. OQ-50 adopted (routine).
  Tests: 8 new (8 steps, equal to step-by-step, reuse, force recompute, dry run writes nothing, failure + resume,
  collection with sources, provider refusing later data).

## Phase 1 · 1.15 settlement: direction + move, idempotent, append-only versions (AC-14, AC-15, AC-27) — 2026-11-28
- `sr/settle/settle.py`: `settle()` starts from the attached t0 quotes (attaching them if missing), finds the end as
  the first sync qualifying quote at or after `target_end_at` within 30 s (D-07), and uses only quotes received by
  the run time (DC §4). Direction: outcome by the locked threshold, hit, Brier; move: `abs_relative_move_pp`,
  `pinball_loss` per quantile, `quantile_hits`. Halt / no start or end quote / basket -> `unsettleable` with the DC
  `invalid_reason`; `reason_text` in Chinese. An identical result returns the reporting version unchanged; a
  changed one (a delayed quote arrived) appends version n+1 and moves the reporting flag. Windows not over ->
  `not_due` (nothing written); abstained predictions are never settled. `quality_summary` keeps unsettleable
  predictions out of the hit-rate denominator (AC-15).
- Tests: five hand-calculated settlements (four direction incl. the ±threshold boundary, one move with pinball and
  hits), three runs = one row, correction -> v2, halt, missing start / end quotes, timing guards. OQ-49 adopted
  (routine). The 1.14 entry's test count was 419 Python tests; `make check` reported 422 with the contract suite.
  Tests: 435 Python.

## Phase 1 · 1.14 inference, atomic publish, immutability (AC-13, AC-27 forecast part) + contract-0.7.3 — 2026-11-28
- **contract-0.7.3**: `model_versions` table (migration `0004_model_versions.sql`; fields unchanged since
  contract-0.7, schema `x-tabled` now true); `prediction_runs.model_version_id` / `baseline_model_version_id`
  reference it; a registered model's content is immutable (trigger), only `status` moves; RLS on. Version constant,
  examples, generated TS / pydantic and the SQL assertions updated. Routine bump under the user's standing approval
  (OQ-48). Training runs now register their models (market_logit + class_frequency baseline; har_vol + gbdt).
- `sr/forecast/run.py` (forecast-0.1, `config/forecast.yaml`): one run + prediction per target
  (regular_60m -> market_logit, regular_60m_move -> gbdt) per snapshot; abstain reasons from market state,
  readiness, data quality, D-18, the sched-0.1 180 s miss rule (`slot_missed`) and sigma (`insufficient_data`);
  sampling rule / primary per D-23 and D-43 (schedule slot, event_first then revision with `supersedes`, …);
  `edge_vs_baseline` = Σ(p − b)² vs class_frequency; locked versions; tier `internal_shadow` unless the model is
  live; artifacts checked against their registered SHA-256 (`ArtifactMismatch`).
- `sr/forecast/features.py`: the feature row at publish time with the dataset's own functions (minute-end mids,
  quotes received by publish, sigma / HAR only from ended windows); `LookaheadError` on later data.
- `sr/forecast/publish.py`: runs + predictions in one transaction, idempotent; `attach_t0` sets t0 (first sync
  qualifying quote after publish, `published_at < t0 quote_ts`), benchmark quote ids, `target_end_at` and moves
  the status to `awaiting_settlement`. The DB trigger rejects changes to published probabilities / quantiles and
  deletes (tested).
- OQ-48 (inference rules) adopted (routine). Tests: 419.

## Phase 1 · 1.13 expected-move models: HAR baseline + GBDT quantiles (AC-27 training part) — 2026-11-28
- `sr/train/models/har_vol.py` (move-0.1, `config/move.yaml`): RV_d / RV_w / RV_m = mean |relative return| over
  the previous 1 / 5 / 22 sessions (earlier sessions only); OLS on logs; quantiles = scale × calibration-split
  ratios; JSON round-trip.
- `sr/train/models/move_quantile.py`: HistGradientBoosting quantile regressors for p50 / p80 / p90 on the HAR
  terms + the 20 market features, seeded, split-conformal shift on the calibration split, no crossing, >= 0.
- `sr/train/move.py`: metrics per subset / group — `pinball_loss`, `interval_coverage` and `interval_width` per
  quantile (`group_key` "all|p80"), `n_effective`; the HAR comparison is `pinball_loss` with
  `reference_model = har_vol` = model − HAR with a trading-day block-bootstrap CI; HAR's own metrics under
  `har_vol:<group>`. `run_training` now dispatches on the dataset target (`regular_60m_move` writes
  `har_vol.json` + `move_quantile.pkl` with SHA-256s).
- OQ-46 confirmed (defaults). OQ-47 (move models) adopted under the user's standing approval for routine defaults.
  Synthetic check: calibration coverage hits nominal within 2 pp; on a 20-day validation split the quantile model's
  pinball is 0.011 below HAR (CI -0.028 to 0.003) and HAR p80 coverage is 77.5 %. Tests: 413.

## Phase 1 · 1.12 first training run: baselines, market_logit, calibration (AC-16) — 2026-11-28
- `sr/train/train.py` (train-0.1, `config/train.yaml`): `market_logit` = L2 multinomial logistic regression
  (scikit-learn, lbfgs, C = 1) on 20 market features (train split; missing -> train median, standardised),
  calibrated on the calibration split by `sr/train/calibrate.py` (isotonic one-vs-rest when >= 300 rows, else
  Platt; JSON-serialisable, applies with numpy). References (D-30): class_frequency, always_flat, persistence
  (latest window ended by the sample time). Metrics per subset (train / calibration / validation) and group (all,
  security): brier, log_loss, hit_rate, ece, coverage, n_effective (trading days), BSS vs each reference with a
  2,000-draw trading-day block-bootstrap CI. `run_training` writes `training_runs` (queued -> training ->
  calibrating -> evaluating -> completed, or failed with an error code) and append-only `training_run_metrics`;
  the model artifact goes to `data/models/<run>/market_logit.json` with its SHA-256. Same dataset + config + seed +
  code returns the existing run (idempotency key). A dataset that failed its availability check, or a row whose t0
  is not after its sample time, fails the run (`availability_check_failed`).
- New dependency: scikit-learn (services/py). OQ-45 confirmed (defaults). OQ-46 (training rules; `model_versions`
  table + contract-0.7.3 proposed for 1.14) proposed, awaiting user. Synthetic check: with a planted signal the
  validation BSS vs class_frequency is +0.31 (CI 0.23-0.39); without one it is -0.005 (CI spans 0). Tests: 404.

## Phase 1 · 1.11 dataset build: splits, embargo, event clusters, exclusions — 2026-11-28
- `sr/labels/window.py`: the 60-minute window label shared with settlement (1.15): t0 = first sync qualifying
  quote after publish (<= 30 s), end = first at/after t0 + 60 min (<= 30 s, D-07), relative return; halt / LULD
  in the window -> `halted`; an unfinished window raises `LookaheadError`.
- `sr/train/dataset.py` (ds-0.1, `config/dataset.yaml`, label lbl-0.1): rows on the 5-minute grid per security,
  D-18 availability, direction class by k × sigma-0.1 from earlier sessions only (`regular_60m_move`: |relative|),
  fs-0.2 features from 1-minute mids labelled by minute end; event clusters (event + 2 sessions, overlaps merged),
  `news_time_unknown`; time-ordered splits 0.70 / 0.10 / 0.10 / 0.10 of trading days with a 1-day embargo and
  cluster integrity (`crosses_split_boundary`); exclusion counts, class balance (quantiles for the move target),
  availability audit; rows + manifest written under `data/datasets/<id>/` (gitignored) and one
  `training_dataset_versions` row. A rebuild is a new version (`parent_dataset_version_id`).
- `FixtureProvider.security_ids`. OQ-44 confirmed (defaults). OQ-45 (dataset rules) proposed, awaiting user.
- Known limit: about 1.5 s per security-day on synthetic 5-second data (the sync search and ~40 pandas feature
  calls per row); a vectorised build is needed before multi-year real data (D-13). Tests: 393.

## Phase 1 · 1.10 security snapshots + same-watermark merge — 2026-11-28
- `sr/snapshot/builder.py` (snapshot-0.1, `config/snapshot.yaml`): `build_snapshot` writes
  `security_state_snapshots` with evidence / market watermarks, market state (pre / regular / post / closed /
  halted), day return vs the previous official close and relative to the peer basket (weights from
  `benchmark_versions`; basket missing -> relative null, AC-40), the event analyses in force since the previous
  regular close (`new_catalyst_found`), explanation status and summary (DC §8.1 wording on no-news days), data
  quality and run state, `last_valid_at`, `valid_until` (D-41) and prediction readiness (policy day ->
  `market_baseline` only, AC-12; outside regular hours `not_applicable`, D-28). The last stock quote is stored in
  `reference_quotes`. Same-watermark merge: an existing `dedupe_key` returns that snapshot, nothing is written
  (also under a concurrent insert). `schedule()` = D-17 5-minute grid + 09:35 / 15:45 ET session checks;
  `replay_session()` builds a whole session from a point-in-time provider. Quotes received after as_of raise.
- 1.09 helpers `quote_row` / `session_type` in `sr/events/reaction.py` are now public.
- OQ-43 confirmed (defaults). OQ-44 (snapshot rules) proposed, awaiting user. Tests: 379 (AC-11 on the synthetic
  fixture: 80 triggers -> 78 snapshots, 5 minutes apart, no event analyses; AC-12; AC-40; merge; quality; D-41;
  look-ahead).

## Phase 1 · 1.09 market reaction + current explanation + time-order check — 2026-11-28
- `sr/events/reaction.py` (reaction-0.1, `config/reaction.yaml`): sync points (D-06, same rule as `sync.py`);
  `ref_before` = last sync point before the evidence's earliest public time, `ref_asof` = last at/before
  `analysis_as_of` (≤ 30 s old); stock / basket / relative return in the DC `market_reaction` fields; basket
  unavailable -> absolute return only, relative null, `missing_reason=benchmark_unavailable` (AC-40); move start =
  opposite extreme of the relative path over the previous 60 min (OQ-43). Cited quotes are written to
  `reference_quotes` (`rq_<ticker>_<yyyymmdd>_<hhmmss>`) so citations resolve. Quotes received after
  `analysis_as_of` raise `LookaheadError`.
- `sr/events/explain.py`: publishes the current explanation as a new analysis version on top of the latest one
  (append-only, supersedes it): `market_reaction`, `market_explanation` + `reasoning_trace` via
  `sr.events.reasoning`, prior cited observed facts carried over, `market_reaction_pending` gap removed,
  `stock_reaction` readiness ready only when the relative return exists. Evidence is read point-in-time.
- Built and tested on synthetic quotes (roadmap-0.2 sequence; no D-13 data). OQ-43 (reaction window and move
  start) proposed, awaiting user. Tests: 366 (AC-10 returns and time order, AC-40, AC-57 timing, negative
  look-ahead tests, synthetic-fixture run, end-to-end DB publish).

## Plan · roadmap-0.2 adopted; trade-execution rules; checker earnings-0.5 (OQ-42) — 2026-11-28
- `docs/roadmap/ROADMAP_EXTENSIONS_CN.md` roadmap-0.2 (user): the 6-month fast route is the current plan. CLAUDE.md
  scope is now research and validation plus, once gates pass, own-funds system trade execution (internal team only);
  new "交易执行" rules: features behind default-off switches, real orders off with no auto-enable, human sign-off,
  Claude never enables real orders, separate `services/trader/` + `trading` schema, paper `BrokerAdapter` first,
  no broker production keys in the repo. Coding sequence: market-data tasks built on synthetic fixtures instead of
  waiting for D-13, then DP Phase 2-3, then contract-1.0 (append-only) and Phase 5-7. MP §12 / DP still say "no
  trade execution"; roadmap-0.2 takes precedence until they are turned into formal phase docs (roadmap §4.5).
- OQ-42 confirmed (defaults). Checker earnings-0.5: values for one metric/basis/period/segment that differ only by
  rounding ("$1.8 billion" vs "$1,779") are one fact; the most precise is kept, rounded copies dropped as
  `rounded_duplicate`; real disagreements stay `conflicting_values`. Eval matching: a prediction with >= 2
  significant figures also matches when it is the gold value rounded (`matching.rounded_match_min_sig: 2`).
  Known limit: trailing zeros are lost in floats, so "$16.0 billion" counts as 2 significant figures. Reviewer
  guide: label the most precise printed figure. Recheck (no API calls): 27 facts restored, 2,229 kept;
  conflicting_values 92 -> 65. Tests: 353.

## Docs · design package 0.7 sync — 2026-11-28
- Synced design package 0.7 (plan/contract/phases 0.7, roadmap 0.1); added training guide, user guide, PPT coverage
  review, business docs. DATA_CONTRACT kept at the repo's contract-0.7.2 (the package copy predates 0.7.1/0.7.2);
  BUILDING_MASTER_PLAN takes the package text (roadmap pointer, internal-team-only §12 / D-33) but keeps
  D-05–D-12 `confirmed`. New `docs/TRAINING_AND_USAGE_GUIDE_CN.md` (the older `docs/business/` copy is kept);
  `docs/roadmap/ROADMAP_EXTENSIONS_CN.md` added; roadmap references point to `roadmap/`.
- Not yet updated: `config/decisions.yaml` D-33 still has the old "对外开放 / 精选用户" wording.

## Phase 1 · 1.18 checker earnings-0.4; recheck keeps reviewer edits — 2026-11-28
- Checker earnings-0.4: bare parenthesised table headers set the scale (`(Millions)`, `(Millions except
  percentages)`, `(Billions)`, `(Thousands)`; parentheses required, so prose "millions of units" does not).
  AMD prints its corporate-data and cash-flow tables this way. All 357 drafts rechecked (no API calls): 31 facts
  restored, all AMD (Data Center operating income, operating cash flow, free cash flow, two year-to-date revenue
  totals); kept facts 2,202; `value_not_in_quote` drops 66 -> 35. 9 restored facts have no period and are
  flagged by `check_labels.py` (110 errors in total) for reviewers.
- `prelabel_extraction.py`: the candidates file records `draft_facts_sha256`, a digest of the draft it wrote
  (`facts_digest` in `sr.llm.labels`). `--recheck` and `--replace-drafts` skip drafts whose facts no longer match,
  i.e. a reviewer has started editing them. Reviewer guide §3 notes this. Tests: 348.

## Phase 1 · 1.18 Claude drafts for policy + news; checker earnings-0.3 — 2026-11-26
- Claude (extract-0.3) drafted the 66 policy/news documents: 66 calls, all succeeded; 447,022 in / 42,466 out
  tokens, ~$2.64 at list price; logged to `llm_calls`. Policy: 0 facts kept (95 candidates, all non-metrics).
  News: 54 facts from 3 releases (AMD and NVIDIA quarterly results, a Marvell merger release).
- Checker earnings-0.3: a metric's unit must fit its kind (`checks.kind_units`; money -> USD, pct -> pct,
  per_share -> USD_per_share), e.g. "revenue outlook ±2%" is rejected as `unit_kind_mismatch`. Same rule in
  `check_labels.py`. All 357 drafts rechecked (no API calls): 2,171 facts kept; 4 newly rejected, all wrong.
- OQ-41 confirmed by user (defaults kept). Tests: 344.

## Phase 1 · 1.18 policy + news documents in the eval corpus — 2026-11-26
- `scripts/fetch_public_corpus.py`: 40 Federal Register policy documents (BIS, presidential documents, USTR,
  NIST CHIPS, ITA) and 26 company newsroom press releases (NVIDIA, AMD, Marvell IR RSS). Size caps, round-robin
  across queries, untrusted feed links limited to the configured press-release prefix, defusedxml, generic
  User-Agent (`LiveTransport(user_agent=…)`), <= 1 request/s. Manifest: 357 documents. OQ-41.
- Manifest rows carry `doc_kind` (policy / news); `doc_kind_for` in `sr.llm.labels`. Reviewer guide §6a.
  No drafts yet for the 66 new documents (Claude prelabel pending approval). Tests: 342.

## Phase 1 · 1.18 reviewer guide + label self-check — 2026-11-26
- `docs/labeling/extraction-v0.md` rewritten as the reviewer guide: workflow, field rules for extract-0.3 labels
  (15 metrics, segment, normalised values, signed losses), what to label / skip (OQ-40), common draft problems
  from the 291 Claude drafts.
- `scripts/check_labels.py`: `--queue` (next documents, stratified, with SEC links), `--text` (normalised text
  quotes come from), lint of label files (verbatim quotes, sha, metric/unit/period format, empty periods,
  duplicates, unscaled values, segment/scope) and progress toward 100 reviewed. `stratified` and `lint_label`
  live in `sr.llm.labels`. Tests: 337.
- OQ-40 labelling scope confirmed by user (defaults kept).

## Phase 1 · 1.18 checker earnings-0.2 + drafts rechecked — 2026-11-26
- Fact checker (OQ-39): table-row scales from the nearest document header above the quote; signed losses and
  declines with a cue word; compact "$0.8B"; USD units reject non-USD currency and NT$-printed numbers.
  `check_facts(..., text)` now takes the document text in the earnings pipeline, the eval and the prelabel
  script; `rule_version` earnings-0.2.
- All 291 Claude drafts rebuilt from saved candidates (no API calls): 1,416 → 2,121 kept facts; value-not-in-
  quote drops 880 → 62; 99 NT$ facts now dropped as `currency_not_supported`. Tests: 333.

## Phase 1 · 1.18 Claude drafts for the full corpus — 2026-11-26
- Claude (extract-0.3) drafted the remaining 271 documents: 271 calls, all succeeded; 1,546,196 in /
  580,874 out tokens, ~$17.80 at list price; every call logged to `llm_calls`. All 291 drafts are now Claude's
  (status draft); 1,313 facts kept, 1,770 dropped by the checker (951 `other` metrics, 880 value-not-in-quote,
  77 conflicts). Most value-not-in-quote drops are table rows whose scale sits only in the table header
  (to be addressed by a checker change + `--recheck`, no new API calls).

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
