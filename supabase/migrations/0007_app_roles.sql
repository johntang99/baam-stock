-- 0007 · Web app roles, row-level policies and request functions (DP 2.07-2.08; DC §6, §10; OQ-63).
-- Role = JWT app_metadata.app_role (set server side only; users cannot change it): viewer < researcher <
-- reviewer < admin. Without a role nothing is readable. No table gets INSERT/UPDATE/DELETE grants: the page's
-- writes go through the security-definer functions at the end, which check the role and the DC rules.
-- The service role (Python) bypasses RLS as before.

do $$
begin
  if not exists (select from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;
grant usage on schema public to anon, authenticated;

-- ---------------------------------------------------------------- role helpers
create or replace function app_jwt() returns jsonb language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb
$$;
create or replace function app_user_id() returns text language sql stable as $$
  select app_jwt() ->> 'sub'
$$;
create or replace function app_role() returns text language sql stable as $$
  select coalesce(app_jwt() -> 'app_metadata' ->> 'app_role', 'none')
$$;
create or replace function app_role_rank(r text) returns int language sql immutable as $$
  select case r when 'viewer' then 1 when 'researcher' then 2 when 'reviewer' then 3 when 'admin' then 4 else 0 end
$$;
create or replace function app_has_role(min_role text) returns boolean language sql stable as $$
  select app_role_rank(app_role()) >= app_role_rank(min_role)
$$;
grant execute on function app_jwt(), app_user_id(), app_role(), app_role_rank(text), app_has_role(text) to anon, authenticated;

-- ---------------------------------------------------------------- read policies (DC §10)
do $$
declare t text;
begin
  -- reference and market data every signed-in role may read
  foreach t in array array['companies', 'securities', 'security_identifiers', 'trading_sessions', 'benchmark_definitions',
      'benchmark_versions', 'prediction_targets', 'forecast_schedules', 'industry_templates', 'company_profile_versions',
      'corporate_actions', 'security_state_snapshots', 'prediction_runs', 'events', 'event_security_links',
      'event_milestones', 'event_analysis_versions', 'forecast_accuracy_rollups', 'reference_quotes'] loop
    execute format('grant select on public.%I to authenticated', t);
    execute format('create policy %I on public.%I for select to authenticated using (app_has_role(''viewer''))',
                   t || '_read_viewer', t);
  end loop;
  -- research and operations data: researcher and above
  foreach t in array array['model_versions', 'training_dataset_versions', 'training_runs', 'training_run_metrics',
      'extraction_eval_runs', 'jobs', 'alerts', 'data_source_health', 'data_sources', 'collection_runs', 'collection_items',
      'onboarding_requests', 'source_documents'] loop
    execute format('grant select on public.%I to authenticated', t);
    execute format('create policy %I on public.%I for select to authenticated using (app_has_role(''researcher''))',
                   t || '_read_researcher', t);
  end loop;
end $$;

grant select on predictions, prediction_settlements, forecast_vs_actual, event_evidence, source_document_versions,
  pipeline_runs, pipeline_run_steps, llm_calls to authenticated;

-- predictions: viewers see only the validated / scenario tiers; researchers see the shadow tier too
create policy predictions_read on predictions for select to authenticated using (
  app_has_role('researcher') or (app_has_role('viewer') and display_tier in ('validated_public', 'scenario_only')));
create policy prediction_settlements_read on prediction_settlements for select to authenticated using (
  exists (select 1 from predictions p where p.prediction_id = prediction_settlements.prediction_id));
create policy forecast_vs_actual_read on forecast_vs_actual for select to authenticated using (
  exists (select 1 from predictions p where p.prediction_id = forecast_vs_actual.prediction_id));

-- evidence by visibility: public -> viewer, internal -> researcher, restricted_review -> admin
create policy event_evidence_read on event_evidence for select to authenticated using (
  case visibility when 'public' then app_has_role('viewer') when 'internal' then app_has_role('researcher')
                  else app_has_role('admin') end);
create policy source_document_versions_read on source_document_versions for select to authenticated using (
  case visibility when 'public' then app_has_role('viewer') when 'internal' then app_has_role('researcher')
                  else app_has_role('admin') end);

-- pipeline runs: viewers see their own runs, researchers see all
create policy pipeline_runs_read on pipeline_runs for select to authenticated using (
  app_has_role('researcher') or (app_has_role('viewer') and requested_by = app_user_id()));
create policy pipeline_run_steps_read on pipeline_run_steps for select to authenticated using (
  exists (select 1 from pipeline_runs r where r.pipeline_run_id = pipeline_run_steps.pipeline_run_id));

create policy llm_calls_read on llm_calls for select to authenticated using (app_has_role('admin'));

-- ---------------------------------------------------------------- request functions (the only page writes)
-- Same key formula as sr.pipeline.orchestrator.idempotency_key, so the worker resumes the queued row.
create or replace function pipeline_idempotency_key(p_security_ids text[], p_target_ids text[], p_as_of timestamptz,
    p_mode text, p_requested_by text) returns text language sql immutable as $$
  select array_to_string(array(select unnest(p_security_ids) order by 1), ',') || '|' ||
         array_to_string(array(select unnest(p_target_ids) order by 1), ',') || '|' ||
         to_char(date_trunc('minute', p_as_of at time zone 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') || '|' ||
         p_mode || '|' || coalesce(p_requested_by, '-')
$$;

create or replace function request_pipeline_run(p_security_ids text[], p_target_ids text[], p_mode text default 'live',
    p_as_of timestamptz default null, p_reuse_policy text default 'reuse_if_unchanged')
returns table (pipeline_run_id text, created boolean)
language plpgsql security definer set search_path = public as $$
declare
  uid text := app_user_id();
  t timestamptz := coalesce(p_as_of, now());
  rid text;
  k text;
  dedupe_s int := 60;  -- AC-35: the same user repeating the same request within 1 minute gets the same run
begin
  if not app_has_role('viewer') or uid is null then raise exception 'not allowed' using errcode = '42501'; end if;
  if p_mode not in ('live', 'replay', 'dry_run') then raise exception 'mode % not allowed here', p_mode using errcode = '22023'; end if;
  if not app_has_role('researcher') and (p_mode <> 'live' or p_reuse_policy <> 'reuse_if_unchanged') then
    raise exception 'viewer may only run live + reuse_if_unchanged' using errcode = '42501';
  end if;
  if p_mode = 'live' then t := now(); end if;  -- replay / dry_run read only data that existed by as_of (provider guard)
  if coalesce(array_length(p_security_ids, 1), 0) = 0 or coalesce(array_length(p_target_ids, 1), 0) = 0 then
    raise exception 'securities and targets required' using errcode = '22023';
  end if;
  if exists (select 1 from unnest(p_security_ids) s(id) left join securities x on x.security_id = s.id
              where x.security_id is null or x.coverage_tier not in ('pilot', 'batch2')) then
    raise exception 'unknown or non-covered security' using errcode = '22023';
  end if;
  select r.pipeline_run_id into rid from pipeline_runs r
   where r.requested_by = uid and r.mode = p_mode::pipeline_mode and r.reuse_policy = p_reuse_policy::reuse_policy
     and r.security_ids @> p_security_ids and r.security_ids <@ p_security_ids
     and r.target_ids::text[] @> p_target_ids and r.target_ids::text[] <@ p_target_ids
     and r.status not in ('failed', 'cancelled')
     and (p_mode <> 'live' or r.as_of > now() - make_interval(secs => dedupe_s))
     and (p_mode = 'live' or date_trunc('minute', r.as_of) = date_trunc('minute', t))
   order by r.as_of desc limit 1;
  if rid is not null then return query select rid, false; return; end if;
  k := pipeline_idempotency_key(p_security_ids, p_target_ids, t, p_mode, uid);
  select r.pipeline_run_id into rid from pipeline_runs r where r.idempotency_key = k;
  if rid is not null then return query select rid, false; return; end if;
  rid := 'pr_' || upper(replace(gen_random_uuid()::text, '-', ''));
  insert into pipeline_runs (pipeline_run_id, security_ids, target_ids, trigger_type, requested_by, mode, as_of, status,
                             reuse_policy, idempotency_key)
  values (rid, p_security_ids, p_target_ids::target_id[], 'on_demand', uid, p_mode::pipeline_mode, t, 'queued',
          p_reuse_policy::reuse_policy, k);
  insert into jobs (job_id, job_type, pipeline_run_id, payload, idempotency_key, run_after)
  values ('job_' || upper(replace(gen_random_uuid()::text, '-', '')), 'pipeline_step', rid,
          jsonb_build_object('pipeline_run_id', rid), 'pipeline|' || rid, now());
  return query select rid, true;
end $$;

create or replace function cancel_pipeline_run(p_pipeline_run_id text) returns text
language plpgsql security definer set search_path = public as $$
declare r pipeline_runs%rowtype;
begin
  select * into r from pipeline_runs where pipeline_run_id = p_pipeline_run_id;
  if not found or not (app_has_role('researcher') or (app_has_role('viewer') and r.requested_by = app_user_id())) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  if r.status in ('queued', 'running') then
    update pipeline_runs set status = 'cancelled', finished_at = now() where pipeline_run_id = p_pipeline_run_id;
    return 'cancelled';
  end if;
  return r.status::text;  -- finished runs keep their status; published parts are never undone
end $$;

-- DC §6 POST refresh: an unexpired snapshot is reused; otherwise one on_demand snapshot job per security per minute
create or replace function request_refresh(p_security_id text) returns table (job_id text, reused_snapshot_id text)
language plpgsql security definer set search_path = public as $$
declare s text; j text; k text;
begin
  if not app_has_role('viewer') then raise exception 'not allowed' using errcode = '42501'; end if;
  if not exists (select 1 from securities where security_id = p_security_id and coverage_tier in ('pilot', 'batch2')) then
    raise exception 'unknown or non-covered security' using errcode = '22023';
  end if;
  select snapshot_id into s from security_state_snapshots
   where security_id = p_security_id and valid_until > now() and data_quality = 'ok'
   order by analysis_as_of desc limit 1;
  if s is not null then return query select null::text, s; return; end if;
  k := 'snap|' || p_security_id || '|on_demand|' || to_char(date_trunc('minute', now() at time zone 'UTC'), 'YYYY-MM-DD"T"HH24:MI');
  insert into jobs (job_id, job_type, payload, idempotency_key, run_after)
  values ('job_' || upper(replace(gen_random_uuid()::text, '-', '')), 'build_snapshot',
          jsonb_build_object('security_id', p_security_id, 'trigger_type', 'on_demand', 'trigger_ref', null,
                             'as_of', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"')),
          k, now())
  on conflict (idempotency_key) do nothing;
  select x.job_id into j from jobs x where x.idempotency_key = k;
  return query select j, null::text;
end $$;

revoke all on function request_pipeline_run(text[], text[], text, timestamptz, text), cancel_pipeline_run(text),
  request_refresh(text) from public;
grant execute on function request_pipeline_run(text[], text[], text, timestamptz, text), cancel_pipeline_run(text),
  request_refresh(text), pipeline_idempotency_key(text[], text[], timestamptz, text, text) to authenticated;

-- Realtime (Supabase only): run progress and new snapshots are pushed to the pages
do $$
begin
  if exists (select from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table pipeline_runs, pipeline_run_steps, security_state_snapshots;
  end if;
end $$;
