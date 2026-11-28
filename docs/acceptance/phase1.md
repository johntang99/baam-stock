# Phase 1 acceptance (DP 1.20)

Date: 2026-11-28 · contract-0.7.4 · roadmap-0.2 · commit at sign-off: see `git log` (this file's commit)

**Result: every Phase 1 acceptance criterion passes on synthetic data.** The real-data re-run still has to happen. That needs the market-data vendor sample (D-13: tasks 1.01 / 1.02) and 100 human-reviewed extraction labels (1.18). Until both exist, nothing here says anything about real NVDA behaviour. All market data used is synthetic (虚构).

How to re-run: `TEST_DATABASE_URL=postgresql://… make check`, which runs ruff, mypy, 493 Python tests, 4 web tests, the contract checks and the Next.js build. A fresh-database replay of the migrations, seeds and SQL assertions is `scripts/db_replay.sh <url>`.

Status key:
- ✅ passes in the test suite.
- ✅ (P2 UI) means the data side passes, and the on-screen part belongs to a Phase 2 page.
- ⏳ means the mechanism passes but the criterion also needs a real-world run that is blocked.

| AC | What it checks | Tests | Status |
|---|---|---|---|
| AC-06 | Every piece of evidence has `received_at` / `available_at`; a missing source time carries a `missing_reason` | `test_evidence_db.py`, `test_evidence_sources.py` | ✅ |
| AC-07 | The same news delivered 3 times gives 1 document version and 0 new analysis versions | `test_evidence_db.py` | ✅ |
| AC-08 | Two concurrent workers: the one with the older watermark cannot overwrite the newer version | `test_events_db.py` | ✅ |
| AC-09 | GAAP and non-GAAP EPS are separate fields; a consensus later than the release gives `expectation_comparison = null` / `no_pre_event_consensus` | `test_earnings_policy_db.py`, `test_factcheck_expectations.py` | ✅ |
| AC-10 | Stock −1 %, basket −3 % shows −1 % absolute and +2 pp relative; news later than the drop is never its confirmed cause | `test_reaction_explain.py`, `test_collection_reasoning.py`, `test_basket.py` | ✅ |
| AC-11 | A no-news day has a snapshot every 5 minutes with no event analyses and `new_catalyst_found = false` | `test_snapshot_builder.py` (the full fixture day: 80 triggers, 78 snapshots) | ✅ |
| AC-12 | Policy day: `allowed_models = ['market_baseline']` | `test_snapshot_builder.py`, `test_earnings_policy_db.py` | ✅ |
| AC-13 | `published_at < t0 quote_ts`; locked version fields set; published probabilities rejected by the DB | `test_forecast.py`, `test_replay_report.py` (the check catches a t0 before publication) | ✅ |
| AC-14 | Settlement run 3 times gives one result; 5 hand-calculated settlements match | `test_settle.py` | ✅ |
| AC-15 | A halt inside the window gives `unsettleable/halted`, kept out of the hit rate | `test_settle.py` | ✅ |
| AC-16 | A completed training run; train / calibration / validation metrics incl. BSS vs the 3 references with block-bootstrap CIs; same seed gives the same metrics; a look-ahead dataset fails the run | `test_train.py` | ✅ |
| AC-27 | Every `regular_60m` forecast has a `regular_60m_move` twin (same snapshot, same t0); settlement writes |move|, pinball and hits; training metrics have pinball and interval coverage vs `har_vol` | `test_forecast.py`, `test_settle.py`, `test_move_models.py` | ✅ |
| AC-30 | At least one `extraction_eval_runs` row; a prompt version below the D-32 gate is refused by feature building | `test_extraction_eval.py` (fake provider) | ⏳ The gate is enforced. The real evaluation needs 100 reviewed labels (1.18) and is a paid run, so it needs approval first |
| AC-34 (P1) | `uv run sr run --security sec_nvda --targets regular_60m,regular_60m_move --mode replay --as-of …` runs the 8 steps, with the same result as step by step; `--mode dry_run` writes no predictions | `test_pipeline.py` (incl. the CLI command itself) | ✅ |
| AC-37 | A 10:1 split: raw `reference_quotes`; a next-session settlement adjusted and matching a hand calculation; unknown ratio gives `unsettleable/corporate_action`; ticker change resolves at its own dates | `test_corporate_actions.py` | ✅ |
| AC-38 | Historical analogues: ≥ 8 cases give n, period, median, IQR, `fallback_level = none`; widening with the level recorded; `insufficient` at sector-wide; no future or same-chain cases | `test_analogues.py` | ✅ |
| AC-39 | Earnings at 16:20 + post-market +8 % gives a `market_move` / `post_market` snapshot and analysis, no `regular_60m`, and a next-session start ≥ 09:31 ET | `scenarios/test_after_hours_move.py` | ✅ |
| AC-40 | After-hours basket short of quotes: `day_relative_pp = null`, "盘后基准不可计算", absolute move kept | `scenarios/test_after_hours_move.py`, `test_snapshot_builder.py` | ✅ (P2 UI) The summary text is written; the monitoring page shows it in Phase 2 |
| AC-41 | Rumour gives analysis v1 marked "未经证实"; 8-K gives v2 superseding v1, evidence `primary_confirmed`, v1 unchanged | `scenarios/test_rumor_to_confirm.py` | ✅ |
| AC-42 | Valuation context complete with `as_of` when there is a source, absent without; feature building refuses it | `test_valuation.py` | ✅ (P2 UI) No licensed source until D-16; the page hides the row in Phase 2 |
| AC-49 (P1) | Snapshots have `run_state` and `valid_until`; `last_valid_at` points to the latest ok; display_state is superseded / expired / settled | `test_validity.py`, `test_snapshot_builder.py` | ✅ |
| AC-52 | Normal day: six slot forecasts, 4 × `regular_60m`, all primary; late 11:30 gives `slot_missed`, not reissued; half day uses only the D-43 slots; event / 5-minute primary rules | `test_schedule_fva.py`, `test_schedule.py`, `test_forecast.py` | ✅ The to-close and next-session slot forecasts abstain with `model_not_validated`, because no model exists yet for those targets (OQ-57) |
| AC-53 | Forecast-path end = locked quantiles; actual-path end = settlement (< 1e-9); residual and inside_p80 by hand; no later data; rollup counts match; n < 30 gives counts only; predictions untouched | `test_schedule_fva.py` | ✅ |
| AC-56 | Collection items cover every item in the run (reposts → kept + duplicates, after-as-of, restricted, failures) | `test_collection_reasoning.py` | ✅ |
| AC-57 | Explanation statements cite evidence or quotes; uncited ones are moved to unexplained; the timing step for news later than the drop | `test_collection_reasoning.py`, `test_reaction_explain.py` | ✅ |
| Report | Any prediction lists its locked inputs, t0 / end quotes, returns, class and settlement reason | `test_replay_report.py` (+ the `/replay` page, `apps/web/lib/replay.test.ts`) | ✅ |

## Still open before Phase 1 can be called done on real data

1. **D-13 vendor sample** (tasks 1.01 MarketDataProvider for the chosen vendor, 1.02 NVDA + basket backfill).
   - Then re-run the dataset build, training, a day replay and this table on real quotes.
   - The dataset build needs a faster version for multi-year data first (CHANGELOG 1.11).
2. **1.18 extraction evaluation.**
   - 100 human-reviewed documents.
   - Then the paid evaluation run, which needs your explicit approval.
   - Then AC-30 on the real prompt.
3. **Models for `regular_to_close` and `next_regular_session`.** These are needed before their slot forecasts can carry probabilities.
4. **Phase 2 UI parts** of AC-40 and AC-42.
5. **Defaults adopted under the user's standing approval:** OQ-43 to OQ-57 in `docs/OPEN_QUESTIONS.md`. Each one says what was chosen.
