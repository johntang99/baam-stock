-- 0001_core · baam-stock core schema (DATA_CONTRACT contract-0.7.1)
-- Single source of truth: packages/contracts/schemas/*.schema.json; columns and enum values must match
-- (enforced by services/py/tests/test_contract_migration.py).
-- All timestamps are timestamptz (UTC). Research only; no trade execution.

-- =====================================================================
-- Enum types
-- =====================================================================
create type time_precision as enum ('ms', 's', 'minute', 'hour', 'day', 'unknown');
create type visibility as enum ('public', 'internal', 'restricted_review');
create type market_state as enum ('pre_market', 'regular', 'post_market', 'closed', 'halted');
create type session_type as enum ('pre_market', 'regular', 'post_market');
create type trigger_type as enum ('scheduled', 'event', 'market_move', 'on_demand', 'session_check', 'user_supplement');
create type target_id as enum ('regular_60m', 'regular_60m_move', 'regular_to_close', 'next_regular_session', 'overnight_gap', 'event_outcome');
create type coverage_tier as enum ('pilot', 'batch2', 'peer_only', 'reference', 'inactive');
create type exchange_code as enum ('XNAS', 'XNYS', 'ARCX', 'XCBO');
create type security_type as enum ('common', 'adr', 'etf', 'index');
create type industry_template as enum ('semiconductor', 'bank', 'biotech', 'generic');
create type corporate_action_type as enum ('split', 'reverse_split', 'cash_dividend', 'special_dividend', 'spin_off', 'ticker_change', 'merger_delisting');
create type session_status as enum ('open', 'early_close', 'closed');
create type data_source_kind as enum ('market_data', 'filing', 'insider_filing', 'company_ir', 'news', 'policy', 'court', 'expectation', 'macro', 'options', 'llm');
create type license_scope as enum ('public', 'licensed_internal', 'licensed_display', 'restricted');
create type source_verification_status as enum ('proposed', 'sample_verified', 'contracted', 'retired');
create type collection_channel as enum ('filing', 'insider_filing', 'company_ir', 'news_wire', 'policy', 'court', 'macro', 'expectation', 'market_data', 'peer_company', 'user_submission');
create type collection_category as enum ('earnings_guidance', 'policy_export', 'customer_demand', 'supply_chain', 'm_and_a', 'litigation', 'management', 'product', 'capital_return', 'macro', 'analyst_rating', 'insider_trade', 'market_data', 'other');
create type collection_disposition as enum ('kept', 'duplicate', 'excluded_irrelevant', 'excluded_after_asof', 'excluded_restricted', 'pending_review', 'fetch_failed');
create type submission_input_kind as enum ('link', 'text', 'file');
create type submission_status as enum ('received', 'fetching', 'verifying', 'verified_primary', 'media_level', 'unverified', 'duplicate', 'rejected_restricted', 'fetch_failed');
create type submission_visibility as enum ('submitter_and_reviewers', 'shared');
create type price_type as enum ('nbbo_mid', 'official_close', 'official_open', 'last_trade');
create type quote_quality_flag as enum ('stale', 'wide_spread', 'halted', 'luld_pause', 'crossed', 'delayed');
create type explanation_status as enum ('supported', 'partial', 'insufficient');
create type data_quality as enum ('ok', 'stale', 'partial', 'failed');
create type run_state as enum ('running', 'complete', 'degraded', 'failed');
create type benchmark_kind as enum ('peer_basket', 'etf_reference');
create type prediction_track as enum ('stock_reaction', 'event_outcome', 'conditional_scenario');
create type output_kind as enum ('class_probs', 'quantiles', 'scenarios');
create type prediction_status as enum ('pending_evaluation', 'published', 'awaiting_trigger', 'awaiting_settlement', 'settled', 'abstained', 'not_triggered', 'unsettleable');
create type abstain_reason as enum ('insufficient_data', 'stale_quote', 'halted', 'benchmark_unavailable', 'conflicting_facts', 'window_insufficient', 'market_closed', 'model_not_validated', 'manual_review', 'low_edge', 'slot_missed');
create type invalid_reason as enum ('no_sync_start_quote', 'no_sync_end_quote', 'halted', 'benchmark_unavailable', 'corporate_action', 'source_unverifiable');
create type display_tier as enum ('validated_public', 'internal_shadow', 'scenario_only');
create type sampling_rule as enum ('user_supplement', 'schedule_slot', 'scheduled_5m', 'event_first', 'market_move_first', 'on_demand', 'revision');
create type training_trigger as enum ('scheduled_weekly', 'manual', 'drift');
create type training_status as enum ('queued', 'building_dataset', 'training', 'calibrating', 'evaluating', 'completed', 'failed', 'cancelled');
create type metric_subset as enum ('train', 'calibration', 'validation', 'holdout', 'shadow');
create type metric_name as enum ('log_loss', 'brier', 'brier_skill_score', 'hit_rate', 'coverage', 'ece', 'n_effective', 'pinball_loss', 'interval_coverage', 'interval_width', 'trigger_rate');
create type reference_model as enum ('class_frequency', 'always_flat', 'persistence', 'har_vol');
create type extraction_field_group as enum ('numeric_fact', 'direction', 'scope', 'certainty');
create type job_type as enum ('ingest_doc', 'analyze_event', 'build_snapshot', 'run_forecast', 'settle_due', 'replay_day', 'build_dataset', 'train', 'evaluate', 'shadow_score', 'pipeline_step', 'onboarding_step', 'source_healthcheck');
create type job_status as enum ('queued', 'running', 'succeeded', 'failed', 'retry_wait', 'dead');
create type pipeline_trigger_type as enum ('on_demand', 'scheduled', 'event', 'market_move', 'user_supplement');
create type pipeline_mode as enum ('live', 'replay', 'dry_run', 'supplement');
create type pipeline_status as enum ('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled');
create type reuse_policy as enum ('reuse_if_unchanged', 'force_recompute');
create type pipeline_step as enum ('collect_evidence', 'verify_dedupe', 'analyze_events', 'build_snapshot', 'readiness_check', 'infer', 'publish', 'schedule_settlement');
create type pipeline_step_status as enum ('pending', 'running', 'succeeded', 'skipped', 'failed', 'retry_wait');
create type onboarding_tier as enum ('pilot', 'batch2', 'peer_only', 'reference');
create type onboarding_stage as enum ('draft', 'profile_review', 'sources_configured', 'backfilling', 'data_validated', 'training', 'shadow', 'active', 'blocked', 'rejected', 'paused');
create type param_policy as enum ('market_sector_only', 'company_offset_candidate');
create type health_status as enum ('healthy', 'degraded', 'down');
create type alert_severity as enum ('info', 'warning', 'critical');
create type alert_kind as enum ('source_down', 'source_latency', 'quote_stale', 'pipeline_failed', 'settlement_backlog', 'drift', 'gate_regression', 'onboarding_blocked');

-- =====================================================================
-- Helper functions
-- =====================================================================
-- probabilities: keys = classes, values in [0,1], sum = 1 ± 1e-6 (DC §1)
create function probabilities_valid(p jsonb) returns boolean
language sql immutable as $$
  select jsonb_typeof(p) = 'object'
     and (select count(*) from jsonb_each(p)) >= 2
     and (select bool_and(jsonb_typeof(v) = 'number' and (v::text)::numeric between 0 and 1) from jsonb_each(p) as t(k, v))
     and abs((select sum((v::text)::numeric) from jsonb_each(p) as t(k, v)) - 1) <= 0.000001
$$;

-- benchmark constituents: [{security_id, weight}], weights sum to 1 (± 1e-5 for rounded seeds)
create function constituents_valid(c jsonb) returns boolean
language sql immutable as $$
  select jsonb_typeof(c) = 'array'
     and jsonb_array_length(c) >= 1
     and abs((select sum((e->>'weight')::numeric) from jsonb_array_elements(c) as e) - 1) <= 0.00001
$$;

create function forbid_mutation() returns trigger
language plpgsql as $$
begin
  raise exception 'IMMUTABLE: % on % is append-only (DATA_CONTRACT §1 versioning)', tg_op, tg_table_name
    using errcode = 'P0001';
end $$;

-- =====================================================================
-- §3.1 companies & securities
-- =====================================================================
create table companies (
  company_id text primary key check (company_id ~ '^co_[a-z0-9_]+$'),
  legal_name text not null,
  cik text unique check (cik ~ '^\d{10}$'),
  sector text not null,
  industry text not null,
  fiscal_calendar jsonb not null default '{}'::jsonb,
  row_version int not null default 1 check (row_version >= 1)
);

create table securities (
  security_id text primary key check (security_id ~ '^sec_[a-z0-9_]+$'),
  company_id text not null,
  security_type security_type not null,
  primary_exchange exchange_code not null,
  currency char(3) not null default 'USD',
  coverage_tier coverage_tier not null,
  primary_benchmark_id text,
  reference_benchmark_id text
);

create table security_identifiers (
  security_id text not null,
  id_type text not null check (id_type ~ '^(ticker|figi|cusip|vendor:[a-z0-9_]+)$'),
  value text not null,
  valid_from date not null,
  valid_to date,
  primary key (security_id, id_type, valid_from),
  unique (id_type, value, valid_from),
  check (valid_to is null or valid_to > valid_from)
);

create table corporate_actions (
  action_id text primary key,
  security_id text not null,
  action_type corporate_action_type not null,
  announced_at timestamptz not null,
  ex_date date not null,
  effective_at timestamptz,
  ratio numeric(20, 6) check (ratio is null or ratio > 0),
  cash_amount numeric(20, 6),
  source_id text not null,
  available_at timestamptz not null
);

create table industry_templates (
  template_id industry_template not null,
  version int not null check (version >= 1),
  key_metrics_default text[] not null,
  event_types_enabled text[] not null,
  official_sources_default jsonb not null,
  exposure_dimensions text[] not null,
  primary key (template_id, version)
);

create table company_profile_versions (
  profile_version_id text primary key,
  company_id text not null,
  version int not null check (version >= 1),
  effective_from timestamptz not null,
  key_metrics text[] not null,
  exposures jsonb not null,
  official_sources jsonb not null,
  priority_rules_version text not null,
  industry_template industry_template not null,
  valuation_peers text[] not null default '{}',
  unique (company_id, version)
);

create table trading_sessions (
  exchange exchange_code not null,
  session_date date not null,
  status session_status not null,
  open_at timestamptz,
  close_at timestamptz,
  source text not null,
  calendar_version text not null,
  primary key (exchange, session_date),
  check ((status = 'closed') = (open_at is null and close_at is null)),
  check (open_at is null or close_at > open_at)
);

-- =====================================================================
-- §3.2 sources, collection, user submissions
-- =====================================================================
create table data_sources (
  source_id text primary key,
  kind data_source_kind not null,
  provider text not null,
  license_scope license_scope not null,
  verification_status source_verification_status not null default 'proposed',
  time_precision_default time_precision not null,
  notes text
);

create table collection_runs (
  collection_run_id text primary key,
  pipeline_run_id text,
  snapshot_id text,
  security_id text not null,
  window_from timestamptz not null,
  window_to timestamptz not null,
  sources_polled jsonb not null default '[]'::jsonb,
  counts jsonb not null default '{}'::jsonb,
  started_at timestamptz not null,
  finished_at timestamptz,
  check (window_to >= window_from)
);

create table collection_items (
  item_id text primary key,
  collection_run_id text not null,
  source_id text not null,
  channel collection_channel not null,
  submission_id text,
  submitted_by text,
  category collection_category not null,
  category_confidence numeric check (category_confidence between 0 and 1),
  title text not null,
  snippet text,
  doc_version_id text,               -- FK to source_document_versions added in Phase 1
  mentions text[] not null default '{}',
  disposition collection_disposition not null,
  duplicate_of text,
  exclusion_reason text,
  relevance numeric check (relevance between 0 and 1),
  linked_event_id text,              -- FK to events added in Phase 1
  linked_evidence_ids text[] not null default '{}',
  occurred_at timestamptz,
  source_published_at timestamptz,
  source_published_precision time_precision,
  received_at timestamptz,
  available_at timestamptz,
  check (disposition <> 'duplicate' or duplicate_of is not null),
  check ((channel = 'user_submission') = (submission_id is not null))
);

create table user_submissions (
  submission_id text primary key check (submission_id ~ '^sub_'),
  submitted_by text not null,
  security_ids text[] not null,
  input_kind submission_input_kind not null,
  url text,
  text text,
  file_path text,
  user_note text,
  user_categories text[] not null default '{}',
  system_categories jsonb not null default '[]'::jsonb,
  final_categories text[] not null default '{}',
  submitted_at timestamptz not null,
  status submission_status not null default 'received',
  verification jsonb not null default '{}'::jsonb,
  item_id text,
  missed_by_system boolean,
  supplement_run_id text,
  visibility submission_visibility not null default 'submitter_and_reviewers',
  check (num_nonnulls(url, text, file_path) = 1),
  check ((input_kind = 'link') = (url is not null)),
  check ((input_kind = 'text') = (text is not null)),
  check ((input_kind = 'file') = (file_path is not null))
);
-- idempotent resubmission of the same URL by the same user (D-47)
create unique index user_submissions_user_url_uq on user_submissions (submitted_by, url) where url is not null;

-- =====================================================================
-- §3.3 market data (1s layer lives in Parquet; PG keeps referenced quotes)
-- =====================================================================
create table reference_quotes (
  quote_id text primary key check (quote_id ~ '^rq_'),
  security_id text not null,
  quote_ts timestamptz not null,
  received_at timestamptz not null,
  session_type session_type not null,
  bid numeric(20, 6),
  ask numeric(20, 6),
  mid numeric(20, 6),
  last numeric(20, 6),
  spread_bp numeric,
  price_type price_type not null,
  quality_flags quote_quality_flag[] not null default '{}',
  is_qualifying boolean not null,
  quote_rule_version text not null,
  vendor_source_id text not null,
  adjustment_basis text not null default 'raw_intraday',
  unique (security_id, quote_ts, price_type, vendor_source_id),
  check (price_type <> 'nbbo_mid' or (bid is not null and ask is not null and mid is not null))
);

-- =====================================================================
-- §3.6 benchmarks
-- =====================================================================
create table benchmark_definitions (
  benchmark_id text primary key check (benchmark_id ~ '^bm_'),
  kind benchmark_kind not null,
  target_security_id text,
  methodology text not null,
  missing_rule text not null
);

create table benchmark_versions (
  benchmark_version_id text primary key check (benchmark_version_id ~ '^bmv_'),
  benchmark_id text not null,
  version int not null check (version >= 1),
  effective_from date not null,
  effective_to date,
  constituents jsonb not null check (constituents_valid(constituents)),
  sync_tolerance_ms int not null default 2000 check (sync_tolerance_ms >= 0),
  defined_at timestamptz not null,
  unique (benchmark_id, version),
  check (effective_to is null or effective_to > effective_from),
  -- defined_at must precede first use (DC §3.6): definition time not after effective start (UTC midnight)
  check (defined_at <= effective_from::timestamp at time zone 'UTC')
);

-- =====================================================================
-- §3.5 security state snapshots
-- =====================================================================
create table security_state_snapshots (
  snapshot_id text primary key check (snapshot_id ~ '^snap_'),
  security_id text not null,
  trigger_type trigger_type not null,
  trigger_ref text,
  analysis_as_of timestamptz not null,
  evidence_watermark timestamptz not null,
  market_watermark timestamptz not null,
  market_state market_state not null,
  session_date date not null,
  last_quote_id text,
  benchmark_version_id text not null,
  day_return_pct numeric,
  day_relative_pp numeric,
  event_analysis_ids text[] not null default '{}',
  new_catalyst_found boolean not null,
  explanation_status explanation_status not null,
  explanation_summary text not null,
  data_quality data_quality not null,
  run_state run_state not null,
  quality_issues jsonb not null default '[]'::jsonb,
  last_valid_at timestamptz,
  valid_until timestamptz not null,
  prediction_readiness jsonb not null,
  dedupe_key text not null unique,
  published_at timestamptz not null,
  -- no time travel: watermarks cannot be after the snapshot's as_of (DC §4 TIME_TRAVEL)
  check (evidence_watermark <= analysis_as_of and market_watermark <= analysis_as_of),
  check (valid_until > analysis_as_of)
);

-- =====================================================================
-- §3.7 / §3.7a targets, schedules, predictions, settlements
-- =====================================================================
create table prediction_targets (
  target_row_id text primary key check (target_row_id ~ '^tgt_'),
  target_id target_id not null,
  target_definition_version text not null,
  track prediction_track not null,
  classes text[] not null,
  threshold_rule jsonb,
  output_kind output_kind not null,
  window_rule jsonb not null,
  min_remaining_min int check (min_remaining_min >= 0),
  event_id text,
  question text,
  deadline_at timestamptz,
  deadline_tz text,
  confirm_sources text[],
  outcome_resolution jsonb,
  no_result_rule text,
  condition jsonb,
  invalid_rules_version text not null,
  check (output_kind <> 'class_probs' or track <> 'stock_reaction' or threshold_rule is not null)
);

create table forecast_schedules (
  schedule_id text primary key,
  schedule_version text not null unique,
  effective_from date not null,
  effective_to date,
  slots jsonb not null,
  half_day_rule jsonb not null,
  holiday_rule text not null,
  miss_rule jsonb not null
);

create table prediction_runs (
  run_id text primary key check (run_id ~ '^run_'),
  trigger_type trigger_type not null,
  trigger_ref text,
  snapshot_id text not null,
  event_analysis_ids text[] not null default '{}',
  feature_snapshot_id text not null,
  model_version_id text not null,          -- FK to model_versions added in Phase 1
  calibration_version text not null,
  baseline_model_version_id text not null,
  evidence_gaps text[] not null default '{}',
  publish_deadline timestamptz not null,
  published_at timestamptz,
  idempotency_key text not null unique
);

create table predictions (
  prediction_id text primary key check (prediction_id ~ '^pred_'),
  run_id text not null,
  target_row_id text not null,
  security_id text not null,
  event_id text,                           -- FK to events added in Phase 1
  status prediction_status not null default 'pending_evaluation',
  probabilities jsonb check (probabilities is null or probabilities_valid(probabilities)),
  predicted_class text,
  interval jsonb,
  sigma_hat_pp numeric check (sigma_hat_pp >= 0),
  threshold_pp numeric check (threshold_pp >= 0),
  move_quantiles jsonb,
  scenarios jsonb,
  edge_vs_baseline numeric,
  display_tier display_tier not null,
  abstain_reason abstain_reason,
  is_primary boolean not null,
  sampling_rule sampling_rule not null,
  schedule_slot_id text,
  schedule_version text,
  scheduled_for timestamptz,
  supersedes_prediction_id text,
  valid_until timestamptz not null,
  locked jsonb not null,
  t0_quote_id text,
  t0_benchmark_quote_ids text[] not null default '{}',
  target_end_at timestamptz,
  published_at timestamptz,
  check (status <> 'abstained' or abstain_reason is not null),
  check (sampling_rule <> 'schedule_slot' or (schedule_slot_id is not null and schedule_version is not null and scheduled_for is not null)),
  -- only scheduled slots are primary-scored with the 5m / on-demand / supplement rules never primary (D-23, D-48)
  check (not (is_primary and sampling_rule in ('scheduled_5m', 'on_demand', 'user_supplement'))),
  check (status in ('pending_evaluation', 'abstained') or published_at is not null),
  check (locked ?& array['target_definition_version', 'quote_rule_version', 'benchmark_version_id', 'calendar_version',
                         'model_version_id', 'calibration_version', 'schema_version', 'sigma_model_version',
                         'sigma_hat_pp', 'threshold_k', 'threshold_pp', 'feature_set_version'])
);
create index predictions_security_status_idx on predictions (security_id, status);

create table prediction_settlements (
  settlement_id text primary key check (settlement_id ~ '^stl_'),
  prediction_id text not null,
  settlement_version int not null check (settlement_version >= 1),
  start_quote_id text,
  end_quote_id text,
  benchmark_start_quote_ids text[] not null default '{}',
  benchmark_end_quote_ids text[] not null default '{}',
  stock_return_pct numeric,
  benchmark_return_pct numeric,
  relative_return_pp numeric,
  outcome_class text,
  hit boolean,
  brier numeric check (brier between 0 and 2),
  abs_relative_move_pp numeric check (abs_relative_move_pp >= 0),
  pinball_loss jsonb,
  quantile_hits jsonb,
  event_outcome text,
  settlement_evidence_ids text[] not null default '{}',
  public_confirmation_at timestamptz,
  legal_effective_at timestamptz,
  triggered boolean,
  triggered_at timestamptz,
  invalid_reason invalid_reason,
  settled_at timestamptz not null,
  is_reporting_version boolean not null,
  reason_text text not null,
  unique (prediction_id, settlement_version)
);
-- at most one reporting version per prediction
create unique index prediction_settlements_reporting_uq on prediction_settlements (prediction_id) where is_reporting_version;

-- =====================================================================
-- §3.8 training & evaluation (model_versions / evaluations / deployments: Phase 1/3)
-- =====================================================================
create table training_dataset_versions (
  dataset_version_id text primary key check (dataset_version_id ~ '^ds_'),
  target_id target_id not null,
  feature_set_version text not null,
  label_version text not null,
  source_versions jsonb not null,
  time_range jsonb not null,
  splits jsonb not null,
  availability_check_passed boolean not null,
  n_rows bigint not null check (n_rows >= 0),
  n_trading_days int not null check (n_trading_days >= 0),
  n_event_clusters int not null check (n_event_clusters >= 0),
  class_balance jsonb not null,
  exclusions jsonb not null,
  parent_dataset_version_id text,
  manifest_path text not null,
  created_at timestamptz not null default now()
);

create table training_runs (
  training_run_id text primary key check (training_run_id ~ '^tr_'),
  dataset_version_id text not null,
  trigger training_trigger not null,
  parent_model_version_id text,
  code_version text not null,
  config_hash text not null,
  random_seed int not null,
  status training_status not null default 'queued',
  stage text,
  started_at timestamptz,
  finished_at timestamptz,
  error jsonb,
  artifact_paths jsonb not null default '{}'::jsonb,
  idempotency_key text not null unique
);

create table training_run_metrics (
  training_run_id text not null,
  seq int not null check (seq >= 0),
  stage text not null,
  iteration int,
  subset metric_subset not null,
  target_id target_id not null,
  group_key text not null,
  metric metric_name not null,
  reference_model reference_model,
  ci95_low numeric,
  ci95_high numeric,
  value numeric not null,
  denominator int check (denominator >= 0),
  recorded_at timestamptz not null,
  primary key (training_run_id, seq),
  check (metric <> 'brier_skill_score' or reference_model is not null)
);

create table extraction_eval_runs (
  eval_run_id text primary key,
  label_set_version text not null,
  llm_provider text not null,
  llm_model text not null,
  prompt_version text not null,
  field_group extraction_field_group not null,
  precision numeric not null check (precision between 0 and 1),
  recall numeric not null check (recall between 0 and 1),
  f1 numeric not null check (f1 between 0 and 1),
  n_docs int not null check (n_docs >= 0),
  passed boolean not null,
  created_at timestamptz not null default now()
);

-- =====================================================================
-- §3.9 jobs queue  (consume with SELECT … FOR UPDATE SKIP LOCKED; lock timeout 5 min)
-- =====================================================================
create table jobs (
  job_id text primary key check (job_id ~ '^job_'),
  job_type job_type not null,
  pipeline_run_id text,
  onboarding_id text,
  payload jsonb not null default '{}'::jsonb,
  idempotency_key text not null unique,
  status job_status not null default 'queued',
  attempts int not null default 0 check (attempts >= 0),
  max_attempts int not null default 5 check (max_attempts >= 1),
  run_after timestamptz not null default now(),
  locked_by text,
  locked_at timestamptz,
  last_error text
);
create index jobs_ready_idx on jobs (run_after) where status in ('queued', 'retry_wait');

-- =====================================================================
-- §3.10 ops: pipeline runs, onboarding, source health, alerts
-- =====================================================================
create table pipeline_runs (
  pipeline_run_id text primary key check (pipeline_run_id ~ '^pr_'),
  security_ids text[] not null,
  target_ids target_id[] not null,
  trigger_type pipeline_trigger_type not null,
  requested_by text,
  mode pipeline_mode not null,
  base_run_id text,
  submission_ids text[] not null default '{}',
  as_of timestamptz not null,
  status pipeline_status not null default 'queued',
  reuse_policy reuse_policy not null default 'reuse_if_unchanged',
  outputs jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  sla_ms int not null default 90000 check (sla_ms >= 0),
  idempotency_key text not null unique,
  check ((mode = 'supplement') = (base_run_id is not null))
);

create table pipeline_run_steps (
  pipeline_run_id text not null,
  step_no int not null check (step_no >= 1),
  step pipeline_step not null,
  security_id text not null,
  status pipeline_step_status not null default 'pending',
  attempt int not null default 0 check (attempt >= 0),
  started_at timestamptz,
  finished_at timestamptz,
  detail jsonb not null default '{}'::jsonb,
  error jsonb,
  job_id text,
  primary key (pipeline_run_id, step_no)
);

create table onboarding_requests (
  onboarding_id text primary key check (onboarding_id ~ '^onb_'),
  ticker text not null,
  cik text,
  primary_exchange exchange_code,
  requested_by text not null,
  approved_by text,
  target_tier onboarding_tier not null,
  stage onboarding_stage not null default 'draft',
  checklist jsonb not null default '[]'::jsonb,
  backfill_report jsonb,
  param_policy param_policy not null default 'market_sector_only',
  profile_version_id text,
  benchmark_version_id text,
  dataset_version_id text,
  model_version_id text,
  blocked_reason text,
  check (stage <> 'blocked' or blocked_reason is not null)
);

create table data_source_health (
  source_id text not null,
  checked_at timestamptz not null,
  status health_status not null,
  latency_p50_ms numeric check (latency_p50_ms >= 0),
  latency_p95_ms numeric check (latency_p95_ms >= 0),
  last_success_at timestamptz,
  error_rate_1h numeric check (error_rate_1h between 0 and 1),
  license_scope license_scope not null,
  verification_status source_verification_status not null,
  note text,
  primary key (source_id, checked_at)
);

create table alerts (
  alert_id text primary key,
  severity alert_severity not null,
  kind alert_kind not null,
  ref text,
  opened_at timestamptz not null,
  acknowledged_by text,
  resolved_at timestamptz,
  message text not null
);

-- =====================================================================
-- Foreign keys (added after all tables because of reference cycles)
-- =====================================================================
alter table securities add foreign key (company_id) references companies;
alter table securities add foreign key (primary_benchmark_id) references benchmark_definitions deferrable initially deferred;
alter table securities add foreign key (reference_benchmark_id) references benchmark_definitions deferrable initially deferred;
alter table security_identifiers add foreign key (security_id) references securities;
alter table corporate_actions add foreign key (security_id) references securities;
alter table corporate_actions add foreign key (source_id) references data_sources;
alter table company_profile_versions add foreign key (company_id) references companies;
alter table collection_runs add foreign key (pipeline_run_id) references pipeline_runs;
alter table collection_runs add foreign key (snapshot_id) references security_state_snapshots;
alter table collection_runs add foreign key (security_id) references securities;
alter table collection_items add foreign key (collection_run_id) references collection_runs;
alter table collection_items add foreign key (source_id) references data_sources;
alter table collection_items add foreign key (submission_id) references user_submissions deferrable initially deferred;
alter table collection_items add foreign key (duplicate_of) references collection_items;
alter table user_submissions add foreign key (item_id) references collection_items deferrable initially deferred;
alter table user_submissions add foreign key (supplement_run_id) references pipeline_runs;
alter table reference_quotes add foreign key (security_id) references securities;
alter table reference_quotes add foreign key (vendor_source_id) references data_sources;
alter table benchmark_definitions add foreign key (target_security_id) references securities deferrable initially deferred;
alter table benchmark_versions add foreign key (benchmark_id) references benchmark_definitions;
alter table security_state_snapshots add foreign key (security_id) references securities;
alter table security_state_snapshots add foreign key (last_quote_id) references reference_quotes;
alter table security_state_snapshots add foreign key (benchmark_version_id) references benchmark_versions;
alter table prediction_runs add foreign key (snapshot_id) references security_state_snapshots;
alter table predictions add foreign key (run_id) references prediction_runs;
alter table predictions add foreign key (target_row_id) references prediction_targets;
alter table predictions add foreign key (security_id) references securities;
alter table predictions add foreign key (supersedes_prediction_id) references predictions;
alter table predictions add foreign key (t0_quote_id) references reference_quotes;
alter table predictions add foreign key (schedule_version) references forecast_schedules (schedule_version);
alter table prediction_settlements add foreign key (prediction_id) references predictions;
alter table prediction_settlements add foreign key (start_quote_id) references reference_quotes;
alter table prediction_settlements add foreign key (end_quote_id) references reference_quotes;
alter table training_dataset_versions add foreign key (parent_dataset_version_id) references training_dataset_versions;
alter table training_runs add foreign key (dataset_version_id) references training_dataset_versions;
alter table training_run_metrics add foreign key (training_run_id) references training_runs;
alter table jobs add foreign key (pipeline_run_id) references pipeline_runs;
alter table jobs add foreign key (onboarding_id) references onboarding_requests;
alter table pipeline_runs add foreign key (base_run_id) references pipeline_runs;
alter table pipeline_run_steps add foreign key (pipeline_run_id) references pipeline_runs;
alter table pipeline_run_steps add foreign key (security_id) references securities;
alter table pipeline_run_steps add foreign key (job_id) references jobs;
alter table onboarding_requests add foreign key (profile_version_id) references company_profile_versions;
alter table onboarding_requests add foreign key (benchmark_version_id) references benchmark_versions;
alter table onboarding_requests add foreign key (dataset_version_id) references training_dataset_versions;
alter table data_source_health add foreign key (source_id) references data_sources;

-- =====================================================================
-- Immutability triggers
-- =====================================================================
-- predictions: after leaving pending_evaluation, probabilities / locked / target_row_id are frozen,
-- and published rows can never be deleted (DC §3.7 约束, §1 软删除).
create function predictions_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    if old.status <> 'pending_evaluation' then
      raise exception 'IMMUTABLE: published prediction % cannot be deleted', old.prediction_id using errcode = 'P0001';
    end if;
    return old;
  end if;
  if old.status <> 'pending_evaluation' and (
       new.probabilities is distinct from old.probabilities
    or new.locked is distinct from old.locked
    or new.target_row_id is distinct from old.target_row_id
    or new.published_at is distinct from old.published_at
    or new.move_quantiles is distinct from old.move_quantiles
    or new.interval is distinct from old.interval
    or new.sigma_hat_pp is distinct from old.sigma_hat_pp
    or new.threshold_pp is distinct from old.threshold_pp) then
    raise exception 'IMMUTABLE: prediction % is published; forecast fields are frozen', old.prediction_id
      using errcode = 'P0001';
  end if;
  return new;
end $$;
create trigger predictions_guard before update or delete on predictions
  for each row execute function predictions_guard();

-- settlements: append-only versions; only is_reporting_version may be switched (DC §4 更正)
create function settlements_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'IMMUTABLE: settlements are append-only' using errcode = 'P0001';
  end if;
  if (to_jsonb(new) - 'is_reporting_version') is distinct from (to_jsonb(old) - 'is_reporting_version') then
    raise exception 'IMMUTABLE: settlement % is append-only; add a new settlement_version', old.settlement_id
      using errcode = 'P0001';
  end if;
  return new;
end $$;
create trigger settlements_guard before update or delete on prediction_settlements
  for each row execute function settlements_guard();

-- append-only tables
create trigger security_state_snapshots_append_only before update or delete on security_state_snapshots
  for each row execute function forbid_mutation();
create trigger collection_items_append_only before update or delete on collection_items
  for each row execute function forbid_mutation();
create trigger reference_quotes_append_only before update or delete on reference_quotes
  for each row execute function forbid_mutation();
create trigger training_run_metrics_append_only before update or delete on training_run_metrics
  for each row execute function forbid_mutation();

-- =====================================================================
-- RLS: enabled everywhere, deny-by-default for anon/authenticated. Role policies (viewer/researcher/
-- reviewer/admin, DC §10) arrive with the web app in Phase 2. The service role bypasses RLS.
-- =====================================================================
do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;
