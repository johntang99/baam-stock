# PPT Blueprint Coverage Review

**Reviewed**: `美股实时研究与短期预测系统开发蓝图.pptx`, all 31 slides plus speaker notes
**Against**: BUILDING_MASTER_PLAN `plan-0.4` (MP), DATA_CONTRACT `contract-0.4` (DC), DEVELOPMENT_PHASES `phases-0.4` (DP), `prototype/`
**Date**: 2026-11-26 (first review against 0.3; updated after the 0.4 changes)

**Legend**: ✅ covered · 🟡 partly covered (named, but missing a work item, acceptance test or field) · ❌ missing

## Summary

| Result | Count | |
|---|---|---|
| ✅ Covered | 96 | All items. The 19 that were partly covered or missing in the 0.3 review were closed in 0.4 (marked "Was 🟡" / "Was ❌" below) |
| 🟡 Partly covered | 0 | Was 15 |
| ❌ Missing | 0 | Was 4 |

"Covered" means the item has a contract field or rule, a build task, an acceptance test and, where it is visible to users, a prototype view. Some covered items still depend on outside data sources that must pass sample checks first (marked `待验证来源` in MP §10): macro vintages, court dockets, valuation data and options. Options stay a Phase 4 placeholder until a source is verified.

No item in the PPT conflicts with the plan. The PPT follows the same three specs and the Brief. Where the PPT is broader than our first release (banks/biotech, multi-point curves), the plan already defers it to Phase 4 on purpose.

---

## Item-by-item

| Slide | Work item | Status | Where it is (or what is missing) |
|---|---|---|---|
| 2 | User questions: what happened, how much is explained, what next | ✅ | MP §1, §2.1 |
| 2 | Scenarios: ordinary day, earnings, policy shock, halt, pre/post-market, weekend | ✅ | DP P1 (3 scenario days), AC-03, AC-15, D-28 |
| 2 | First acceptance: NVDA 60-min replay | ✅ | DP Phase 1 |
| 2 | Scope: market + event evidence, pending events, user pages, R&D console | ✅ | MP §1.1 |
| 3 | Step 1 collection with version, precision, availability | ✅ | DC §3.2, §1.1 |
| 3 | Step 2 event cards and security snapshots | ✅ | DC §3.4–3.5, DP P1-2～P1-4 |
| 3 | Step 3 forecast from the first qualifying quote after publication, auto-settle | ✅ | DC §3.7, DP P1-5/P1-6 |
| 3 | Training back office: shadow, approval, rollback | ✅ | DP Phase 3 |
| 4 | Pilot NVDA, AMD, AVGO, MU; batch 2 TSM, MRVL | ✅ | D-03; onboarding flow for TSM/MRVL (P3-7) |
| 5 | 11 driver categories ①–⑪ | ✅ | `events.category` enum covers all 11 |
| 5 | ⑥ Macro (Fed, BLS, BEA) with **first-release values vs consensus** | ✅ | Was 🟡. `macro_releases` with ALFRED first-release vintages (DC §3.3), `MacroProvider` adapter (MP §3.2, D-15), task 2.19, AC-46 |
| 5 | ⑧ Litigation: court dockets | ✅ | Was ❌. `docket_entries` (DC §3.3), `DocketSource` adapter for CourtListener/RECAP with PACER for key cases (D-15), task 2.20, AC-47 |
| 5 | ⑨ Insider trades (Form 4), estimate revisions | ✅ | Was 🟡. `insider_transactions` from EDGAR Form 4 and the `revision_of_exp_id` estimate-revision chain (DC §3.3), task 2.21, AC-48 |
| 5 | ⑩ Options flow, index rebalances, volume | ✅ | Was 🟡. Rebalances and volume in fs-0.2 (D-31). Options: `options_snapshots` + `OptionsProvider` placeholder, gated behind source verification, Phase 4, AC-51 |
| 5 | ⑪ Pending events ranked by exposure, surprise, urgency | ✅ | DC `priority` jsonb, `rule_version` |
| 6 | Fact sources (SEC, IR, calls, BIS, Federal Register) | ✅ | D-15, P1-1, P2-4 |
| 6 | Licensed newswire for discovery; original source recorded | ✅ | `origin_doc_id`, `independent_origin_key` |
| 6 | Historical consensus snapshots before publication | ✅ | DC `expectation_snapshots`, D-16 |
| 6 | Phase 0 data acceptance: timestamps, latency, depth, sessions, fields, license, display | ✅ | DP P0-D, `docs/data_procurement.md` |
| 6 | Compliance: restricted review for suspected leaks | ✅ | `visibility=restricted_review`, AC-25, runbook |
| 7 | Six timestamps, UTC storage, exchange-time display | ✅ | DC §1.1 |
| 7 | Replay uses only data available before the cut; real vs simulated arrival | ✅ | `arrival_mode`, AC-16 negative test |
| 7 | Date-only sources excluded from intraday surprise | ✅ | DC §1.1 replay rule |
| 7 | Evidence archive: hash, locator, license, corrections | ✅ | DC §3.2 |
| 7 | Failure visibility: delays, gaps, stale quotes, logs with recovery | ✅ | P2-5 quality report, P2-10 alerts, runbooks |
| 8 | Company profile (IDs, ticker validity, fiscal calendar, exposures, regulators) | ✅ | DC §3.1 |
| 8 | SOXX reference + pre-fixed peer basket ex-target | ✅ | D-08, DC §3.6 |
| 8 | Replay with tickers, **corporate actions** and benchmark versions as of that time | ✅ | Was 🟡. `corporate_actions` table and rules (DC §3.1, D-40), task 1.21, AC-37 |
| 8 | Cross-industry method (banks, biotech) | ✅ | Was 🟡. `industry_templates` (semiconductor/bank/biotech/generic) and `company_profile_versions.industry_template` (DC §3.1, D-42), task 2.23, AC-50 (same policy → chip vs bank test company). Banks and biotech stay out of the first-release list (D-03) |
| 9 | Fact extraction with source location; program checks calculations | ✅ | P1-2, P1-10, D-32 |
| 9 | Merge rules, idempotency, stable keys, ambiguous → review | ✅ | `identity_key`, AC-07 |
| 9 | Multi-dimensional status | ✅ | `events` three status fields |
| 9 | Key conflicts freeze affected handoff | ✅ | readiness `manual_review`, `abstain_reason=conflicting_facts` |
| 10 | Surprise vs same-basis consensus, GAAP/non-GAAP, fiscal weeks, missing consensus | ✅ | AC-09, `fiscal_calendar` |
| 10 | Pending progress vs previous public milestone; extensions keep the original deadline | ✅ | `event_milestones`, S3 rule in DC |
| 10 | Impact chain fact → exposure → metric → horizon; two companies can diverge | ✅ | DC `impact`, Phase 2 AMD-only test |
| 10 | Priority in four dimensions; rumors flagged unverified | ✅ | DC `priority`, `media_report` |
| 11 | Current price, source, quote time, comparison start, session | ✅ | snapshot + `market_reaction` |
| 11 | **Valuation context** when explaining a price level | ✅ | Was ❌. `market_explanation.valuation_context` (DC §3.4), task 1.24, AC-42; prototype stock page shows it as background only |
| 11 | Absolute and relative together (−3% vs +2pp) | ✅ | AC-10 |
| 11 | Attribution with counter-evidence; time order; unexplained part | ✅ | `market_explanation`, AC-10 |
| 11 | **Historical analogues** by subtype, stage, industry, surprise and first reaction; sample size, distribution, fallback | ✅ | Was 🟡. Retrieval rules DC §3.4a (`hc-0.1`, min 8 cases, fallback levels, no self-match), D-38, task 1.22, AC-38; prototype events page shows the card, including fallback and "insufficient" |
| 12 | Triggers (news, event update, market move, schedule, on-demand), 5-minute default | ✅ | D-17, `trigger_type` |
| 12 | Flash and full analysis, keeping both versions | ✅ | `analysis_kind` |
| 12 | Handoff fields | ✅ | DC §3.5 |
| 12 | Run states (normal, pending review, partial, insufficient, halted, closed, stale, failed) with reason and last valid time | ✅ | Was 🟡. Snapshot `run_state`, `quality_issues`, `last_valid_at` (DC §3.5), tasks 1.23/2.22, AC-49; prototype monitor and stock pages show quality badges and last valid time |
| 13 | Executive/litigation milestones (motion, hearing, injunction, ruling, appeal, enforcement) | ✅ | `milestone_type` list |
| 13 | Investment/M&A milestones with preconditions and authoritative confirmation | ✅ | `event_milestones`, `confirm_sources` |
| 13 | Policy: speech → proposed rule → final text → effective → license → shipment | ✅ | Was 🟡. Milestone types now include `official_statement`, `proposed_rule`, `comment_period_end`, `rule_effective`, `license_applied`, `shipment_confirmed` (DC §3.4) |
| 13 | Settleable question: decision body, exclusive outcomes, deadline, time zone, evidence | ✅ | `prediction_targets` event fields |
| 14 | Event-outcome prediction settled by its own rules | ✅ | Was 🟡. `outcome_resolution` + `no_result_rule`, public vs legal-effective times (DC §3.7, D-39), task 2.17, AC-43; prototype shows the rules card |
| 14 | Price prediction, with market baseline on no-news days | ✅ | AC-11 |
| 14 | **Conditional prediction** (e.g. if the deal terminates), triggers counted separately | ✅ | Was 🟡. `prediction_targets.condition`, `triggered`, `trigger_rate` metric (DC §3.7–3.8, D-39), task 2.18, AC-45; prototype shows an "awaiting trigger" card |
| 14 | New forecast after official result; prior, conditional and new kept separate | ✅ | `supersedes_prediction_id`, `sampling_rule` |
| 15 | 60-min, to-close, next-session windows with boundaries | ✅ | D-02, D-10, D-18, AC-03 |
| 15 | Overnight gap and extended hours defined separately | ✅ | `overnight_gap`, D-28 |
| 16 | Start/end quotes, official close | ✅ | D-07, D-11 |
| 16 | Absolute, relative, frozen thresholds | ✅ | D-09 (volatility-scaled) |
| 16 | Spread, stale, unsynced, halt, corporate action, missing → rules; corrections → new settlement version | ✅ | D-12, DC §4 (corporate action see slide 8) |
| 16 | Published forecasts unchanged; primary-score selection | ✅ | D-23, DB trigger |
| 17 | Publishing conditions; show explanation and missing reason | ✅ | readiness + `abstain_reason` |
| 17 | Refresh and **expiry**: show validity, update time, session, reference quote, version | ✅ | Was 🟡. `valid_until` on snapshots and predictions (DC §3.5/3.7, D-41), AC-49; prototype shows "valid until" |
| 17 | Chart: solid history, publish and start markers, endpoint median and interval | ✅ | Prototype forecast page |
| 17 | UI separates mock example, approved forecast, **expired** and pending settlement | ✅ | Was 🟡. Derived `display_state` (current / superseded / expired / settled), task 2.22, AC-49; prototype forecast pages show superseded (NVDA to-close) and expired (AMD 60m) |
| 18 | NVDA 10:20 replay; baseline and event model locked in a common window | ✅ | DC §8.1, `baseline_model_version_id` |
| 18 | Page shows source text, availability, two probabilities, quotes, threshold, settlement reason | ✅ | Prototype replay page. Showing both model probabilities is in the R&D replay (S3 §9.1) |
| 19 | Inputs before the cut, settled labels, frozen versions | ✅ | `training_dataset_versions` |
| 19 | Separate labels per window, interval and event | ✅ | DC §3.7–3.8 |
| 19 | Sample coverage across day types; exclusion statistics | ✅ | `exclusions`, E-7 |
| 19 | Time splits, embargo, event clusters, true holdout | ✅ | D-19 |
| 20 | Baselines; regularized small model | ✅ | D-24, D-30 |
| 20 | Event features compared on the same time points | ✅ | Phase 3 |
| 20 | Market → sector → company layers; thin companies use validated layers | ✅ | D-36, P3-2 |
| 20 | Language model only extracts and explains; statistical model makes probabilities | ✅ | MP §7.1 |
| 21 | Weekly / manual / drift triggers; artifacts; failures logged | ✅ | D-22, `training_runs` |
| 21 | Live shadow; approval by scope; rollback | ✅ | Phase 3, AC-20～AC-22 |
| 22 | Hit rate, confusion matrix, Brier, calibration | ✅ | `training_run_metrics`, prototype validation page |
| 22 | Coverage denominators, interval **coverage and width** | ✅ | Was 🟡. `interval_width` metric (DC §3.8), task 3.04, AC-28 (P3 extension) |
| 22 | Fair comparison, day/cluster bootstrap | ✅ | D-30 |
| 22 | Pre-registered gates and segment reports | ✅ | D-21, E-7 |
| 23 | 200/180/100 coverage example | ✅ | AC-19, DC §8.3 |
| 24 | R&D pages: runs, snapshots, metrics, parameters, evaluation, replay, approval, role access | ✅ | Prototype admin, DP Phase 3 |
| 25 | Next.js / Supabase / Python roles; replaceable providers; observability | ✅ | MP §3 |
| 26 | Contract entities and audit relations | ✅ | DC §2–3 |
| 27 | Prototype pages: monitor, forecast, events + replay, R&D console | ✅ | `prototype/` |
| 27 | Monitor page shows **data quality** | ✅ | Was 🟡. See slide 12; prototype monitor cards show quality and run state |
| 28 | Phase 0–3 and later | ✅ | DP |
| 29 | Time edge cases (11:00 news, weekend) | ✅ | AC-03 |
| 29 | **After-hours +8% belongs to past moves, not a hit** | ✅ | Was 🟡. AC-39 (and AC-40 for missing after-hours benchmark), task 1.25 |
| 29 | Info edge cases (reposts, late consensus, no news, late tasks) | ✅ | AC-07～AC-11, AC-08 |
| 29 | Halt / missing quote; <60 min skip | ✅ | AC-15, AC-03 |
| 29 | **Regulatory clearance while closing is still pending** | ✅ | Was ❌. AC-44 and the D-39 rule; prototype deal event shows clearance and closing as separate milestones |
| 29 | Model acceptance (same sample, accuracy up/coverage down, training failure, rollback) | ✅ | AC-19～AC-22 |
| 30 | Master Plan, Contract, Phases, HTML prototype, browser-tested | ✅ | Delivered |
| 30 | **Review output: each item marked covered / partial / missing / conflict, with fix priority** | ✅ | Was ❌. MP §10 traceability table now has Status and Priority columns, plus 16 new rows |
| 31 | Spec index and precedence | ✅ | MP §0 |

Counts are rows in this table (96 work items across the 31 slides).

---

## Recommended additions (all done in 0.4)

All eight were folded into plan-0.4 / contract-0.4 / phases-0.4. Actual effort in the work breakdown is about 28 person-days (the estimate below was 23), taking Phases 0–3 from about 183 to about 211 person-days.

Original list, ranked by impact on correctness first:

| # | Gap | What to add | Where | Size |
|---|---|---|---|---|
| R1 | **Historical-analogue lookup** (slide 11, S2 §3.6) | Versioned query (subtype, stage, window, quote basis, then industry, exposure, surprise, first reaction); outputs n, period, median and IQR of relative return, continuation/reversal rate with denominator, fallback flag. Tests: the case never matches itself or its older versions; only cases whose result was known at analysis time; "insufficient samples" shown | DC `historical_cases` schema + `case_query_version`; DP new task in Phase 1–2 + AC | ~5 person-days |
| R2 | **Event-outcome settlement and conditional forecasts** (slide 14) | Build task to create questions, settle at deadline (confirmed / terminated / no public confirmation / unverifiable), record publication vs legal-effective time; conditional forecasts with trigger window, `not_triggered` counts and trigger rate | DP Phase 2 task + 2 ACs | ~6 person-days |
| R3 | **Missing edge-case tests** (slide 29, S2/S3 §7) | ACs for: after-hours +8% excluded; after-hours stock with no synced benchmark → relative return empty with reason; regulatory clearance ≠ closing; CEO rumor → confirmation keeps old version | DP Phase 1–2 | ~2 person-days |
| R4 | **Corporate actions** (slides 8, 16) | `corporate_actions` table (split, reverse split, ticker change, spin-off, special dividend; effective date) used by replay and settlement invalidation | DC + DP Phase 1 | ~2 person-days |
| R5 | **More source adapters** (slide 5) | Macro (Fed/BLS/BEA releases + ALFRED vintages for replay), court dockets (PACER or a docket service), SEC Form 4. Add to D-15 as "to verify" and to the Phase 2–3 data track | MP D-15, DP | ~6 person-days |
| R6 | **Valuation context** (slide 11) | Optional `valuation_context` in `market_explanation`: forward EPS snapshot as-of, P/E basis, source | DC | <1 person-day |
| R7 | **Validity, expiry and quality display** (slides 12, 17, 27) | `valid_until` on snapshots/predictions; UI badges for data quality, last valid update, superseded/expired; prototype update | DC + prototype | ~1 person-day |
| R8 | **Interval width metric + traceability status column** (slides 22, 30) | Add `interval_width` to metrics; add Status/Priority columns to MP §10 | DC/MP | <1 person-day |

R1–R4 matter most because they affect whether forecasts and settlements are correct. R5 affects which drivers can be analyzed at all, and its cost depends on data contracts. R6–R8 are small.

Estimated at about 23 person-days; the 0.4 work breakdown came to about 28, roughly 3 extra weeks across Phases 1–2 for the 2-engineer team.
