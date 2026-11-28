-- contract-0.7.4 (DP 1.26; DC §3.7a; D-44; AC-53): forecast_vs_actual + forecast_accuracy_rollups as tables
-- (fields unchanged since contract-0.5). Both are DERIVED: rebuilt by sr.eval.fva / sr.eval.rollups after each
-- settlement batch from predictions, settlements and quotes; they never feed back into predictions (read-only
-- comparison data, DC §3.7a rule). forecast_vs_actual is a table rather than a SQL materialized view because the
-- actual minute path comes from the 1-second quote layer (Parquet), not from Postgres.

create table forecast_vs_actual (
  prediction_id text primary key references predictions,
  security_id text not null,
  session_date date not null,
  target_id target_id not null,
  schedule_slot_id text,
  t0_at timestamptz,
  target_end_at timestamptz,
  forecast_path jsonb not null,
  actual_path jsonb not null default '[]'::jsonb,
  status prediction_status not null,
  outcome_class text,
  hit boolean,
  brier numeric,
  inside_p80 boolean,
  inside_p90 boolean,
  residual_pp numeric,
  abs_move_error_pp numeric
);
create index forecast_vs_actual_security_day_idx on forecast_vs_actual (security_id, session_date);

create type rollup_window as enum ('session', 'rolling_20d', 'rolling_60d', 'since_live');

create table forecast_accuracy_rollups (
  security_id text not null,
  target_id target_id not null,
  group_key text not null,
  "window" rollup_window not null,
  n_published int not null check (n_published >= 0),
  n_settled int not null check (n_settled >= 0),
  n_abstained int not null check (n_abstained >= 0),
  n_unsettleable int not null check (n_unsettleable >= 0),
  hit_rate numeric,
  brier numeric,
  bss_class_frequency numeric,
  coverage_p80 numeric,
  coverage_p90 numeric,
  mean_interval_width_pp numeric,
  mean_residual_pp numeric,
  mean_abs_residual_pp numeric,
  calibration_bins jsonb not null default '[]'::jsonb,
  model_version_ids text[] not null default '{}',
  computed_at timestamptz not null,
  primary key (security_id, target_id, group_key, "window")
);

alter table forecast_vs_actual enable row level security;
alter table forecast_accuracy_rollups enable row level security;
