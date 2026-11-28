-- contract-0.7.3 (DP 1.14; DC §3.8): the model_versions table (fields unchanged since contract-0.7; schema-only until
-- now). Training runs register their models here (status candidate); prediction_runs reference them.

create type model_family as enum ('class_frequency', 'always_flat', 'persistence', 'har_vol', 'market_logit',
                                  'market_event_logit', 'gbdt', 'two_stage');
create type param_layers as enum ('market', 'market_sector', 'market_sector_company');
create type model_status as enum ('candidate', 'shadow', 'pending_approval', 'live', 'retired', 'rejected', 'rolled_back');

create table model_versions (
  model_version_id text primary key check (model_version_id ~ '^mdl_'),
  training_run_id text not null references training_runs,
  target_id target_id not null,
  model_family model_family not null,
  param_layers param_layers not null,
  scope jsonb,
  features text[],
  hyperparams jsonb,
  coefficients_path text,
  calibration_version text,
  publish_threshold jsonb,
  artifact_sha256 text,
  status model_status not null default 'candidate'
);
create index model_versions_run_idx on model_versions (training_run_id);

-- a published forecast always names a registered model (and the baseline produced alongside it)
alter table prediction_runs add foreign key (model_version_id) references model_versions;
alter table prediction_runs add foreign key (baseline_model_version_id) references model_versions;

-- a model's fitted content never changes after registration; only its lifecycle status moves (DC §5)
create function model_versions_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'IMMUTABLE: model version % cannot be deleted', old.model_version_id using errcode = 'P0001';
  end if;
  if (to_jsonb(new) - 'status') is distinct from (to_jsonb(old) - 'status') then
    raise exception 'IMMUTABLE: model version % is fixed; register a new version', old.model_version_id
      using errcode = 'P0001';
  end if;
  return new;
end $$;
create trigger model_versions_guard before update or delete on model_versions
  for each row execute function model_versions_guard();

-- RLS on (deny-by-default, DC §10 policies arrive in Phase 2), as for every public table
alter table model_versions enable row level security;
