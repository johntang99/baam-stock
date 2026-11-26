-- Assertions for 0001_core + seeds (AC-01, immutability, contract checks). Runs in a transaction, rolled back.
begin;

-- ---------- AC-01: universe & benchmarks ----------
do $$
declare n int; r record;
begin
  select count(*) into n from securities where coverage_tier = 'pilot';
  if n <> 4 then raise exception 'AC-01: expected 4 pilot securities, got %', n; end if;
  select count(*) into n from securities where coverage_tier = 'batch2';
  if n <> 2 then raise exception 'AC-01: expected 2 batch2 securities, got %', n; end if;
  select count(*) into n from securities where coverage_tier = 'reference';
  if n <> 5 then raise exception 'expected 5 reference securities (QQQ, SPY, SMH, SOXX, ^VIX), got %', n; end if;
  select count(*) into n from securities where coverage_tier = 'peer_only';
  if n <> 7 then raise exception 'expected 7 peer_only basket constituents, got %', n; end if;

  for r in
    select s.security_id, s.primary_benchmark_id, bd.target_security_id, bv.constituents
    from securities s
    join benchmark_definitions bd on bd.benchmark_id = s.primary_benchmark_id
    join benchmark_versions bv on bv.benchmark_id = bd.benchmark_id and bv.version = 1
    where s.coverage_tier = 'pilot'
  loop
    if r.primary_benchmark_id <> 'bm_semis_peer_ex_' || substr(r.security_id, 5) then
      raise exception 'AC-01: % primary benchmark is %', r.security_id, r.primary_benchmark_id; end if;
    if r.target_security_id <> r.security_id then
      raise exception 'AC-01: benchmark target mismatch for %', r.security_id; end if;
    if jsonb_array_length(r.constituents) <> 11 then
      raise exception 'AC-01: % basket has % constituents', r.security_id, jsonb_array_length(r.constituents); end if;
    if exists (select 1 from jsonb_array_elements(r.constituents) e where e->>'security_id' = r.security_id) then
      raise exception 'AC-01: % basket contains itself', r.security_id; end if;
    if abs((select sum((e->>'weight')::numeric) from jsonb_array_elements(r.constituents) e) - 1) > 1e-9 then
      raise exception 'AC-01: % basket weights do not sum to 1', r.security_id; end if;
    if exists (select 1 from jsonb_array_elements(r.constituents) e
               where not exists (select 1 from securities x where x.security_id = e->>'security_id')) then
      raise exception 'AC-01: % basket references unknown security', r.security_id; end if;
  end loop;
  select count(*) into n from securities s where s.coverage_tier = 'pilot' and s.primary_benchmark_id is null;
  if n <> 0 then raise exception 'AC-01: pilot without primary benchmark'; end if;

  select count(*) into n from securities where coverage_tier in ('pilot', 'batch2') and reference_benchmark_id = 'bm_soxx_ref';
  if n <> 6 then raise exception 'pilot+batch2 should reference bm_soxx_ref, got %', n; end if;

  select count(*) into n from company_profile_versions where industry_template = 'semiconductor';
  if n <> 4 then raise exception 'pilot companies need industry_template=semiconductor profiles, got %', n; end if;
  select count(*) into n from industry_templates;
  if n <> 4 then raise exception 'expected 4 industry templates, got %', n; end if;

  select count(*) into n from prediction_targets where target_definition_version = 'td-0.2';
  if n <> 4 then raise exception 'expected 4 td-0.2 targets, got %', n; end if;
  if (select (threshold_rule->>'k')::numeric from prediction_targets where target_row_id = 'tgt_regular_60m_v1') <> 0.25 then
    raise exception 'tgt_regular_60m_v1 threshold k must be 0.25 (D-09)'; end if;
  if (select output_kind::text from prediction_targets where target_row_id = 'tgt_regular_60m_move_v1') <> 'quantiles' then
    raise exception 'tgt_regular_60m_move_v1 must output quantiles'; end if;
  if (select jsonb_array_length(slots) from forecast_schedules where schedule_version = 'sched-0.1') <> 6 then
    raise exception 'sched-0.1 must have 6 slots'; end if;
  raise notice 'AC-01 seed assertions passed';
end $$;

-- ---------- fixtures for trigger tests ----------
insert into reference_quotes (quote_id, security_id, quote_ts, received_at, session_type, bid, ask, mid, spread_bp,
  price_type, quality_flags, is_qualifying, quote_rule_version, vendor_source_id)
values ('rq_test_t0', 'sec_nvda', '2026-12-01T15:20:02Z', '2026-12-01T15:20:02.1Z', 'regular', 182.40, 182.42, 182.41,
  1.1, 'nbbo_mid', '{}', true, 'qr-0.1', 'src_fixture_synthetic');

insert into security_state_snapshots (snapshot_id, security_id, trigger_type, analysis_as_of, evidence_watermark,
  market_watermark, market_state, session_date, benchmark_version_id, new_catalyst_found, explanation_status,
  explanation_summary, data_quality, run_state, valid_until, prediction_readiness, dedupe_key, published_at)
values ('snap_test_1', 'sec_nvda', 'scheduled', '2026-12-01T15:20:00Z', '2026-12-01T15:18:44Z', '2026-12-01T15:19:59Z',
  'regular', '2026-12-01', 'bmv_semis_peer_ex_nvda_v1', false, 'partial', 'synthetic test', 'ok', 'complete',
  '2026-12-01T15:30:00Z', '{"event_outcome":{"status":"not_applicable","reason":"x"},"stock_reaction":{"status":"ready","reason":"y"}}',
  'test|1', '2026-12-01T15:20:00.6Z');

insert into prediction_runs (run_id, trigger_type, snapshot_id, feature_snapshot_id, model_version_id, calibration_version,
  baseline_model_version_id, publish_deadline, idempotency_key)
values ('run_test_1', 'scheduled', 'snap_test_1', 'fs_test', 'mdl_test', 'cal_test', 'mdl_base', '2026-12-01T15:21:00Z', 'k1');

insert into predictions (prediction_id, run_id, target_row_id, security_id, status, probabilities, display_tier,
  is_primary, sampling_rule, valid_until, locked, published_at, sigma_hat_pp, threshold_pp)
values ('pred_test_1', 'run_test_1', 'tgt_regular_60m_v1', 'sec_nvda', 'published',
  '{"outperform":0.38,"flat":0.35,"underperform":0.27}', 'internal_shadow', false, 'scheduled_5m',
  '2026-12-01T16:20:02Z',
  '{"target_definition_version":"td-0.2","quote_rule_version":"qr-0.1","benchmark_version_id":"bmv_semis_peer_ex_nvda_v1","calendar_version":"cal-2026.11","model_version_id":"mdl_test","calibration_version":"cal_test","schema_version":"contract-0.7.1","sigma_model_version":"sigma-0.1","sigma_hat_pp":0.6,"threshold_k":0.25,"threshold_pp":0.15,"feature_set_version":"fs-0.2"}',
  '2026-12-01T15:20:00.8Z', 0.60, 0.15);

-- helper: expect a statement to fail
create function pg_temp.expect_fail(stmt text, label text) returns void language plpgsql as $$
begin
  begin
    execute stmt;
  exception when others then
    raise notice 'ok (rejected): % -- %', label, sqlerrm;
    return;
  end;
  raise exception 'EXPECTED FAILURE did not happen: %', label;
end $$;

-- ---------- AC-13 DB part: frozen after publish ----------
select pg_temp.expect_fail($$update predictions set probabilities = '{"outperform":0.5,"flat":0.25,"underperform":0.25}' where prediction_id = 'pred_test_1'$$, 'update probabilities after publish');
select pg_temp.expect_fail($$update predictions set locked = locked || '{"threshold_k":0.3}' where prediction_id = 'pred_test_1'$$, 'update locked after publish');
select pg_temp.expect_fail($$update predictions set target_row_id = 'tgt_regular_to_close_v1' where prediction_id = 'pred_test_1'$$, 'update target_row_id after publish');
select pg_temp.expect_fail($$delete from predictions where prediction_id = 'pred_test_1'$$, 'delete published prediction');
-- status progression is allowed
update predictions set status = 'awaiting_settlement', t0_quote_id = 'rq_test_t0', target_end_at = '2026-12-01T16:20:02Z'
  where prediction_id = 'pred_test_1';

-- ---------- contract CHECKs ----------
select pg_temp.expect_fail($$insert into predictions (prediction_id, run_id, target_row_id, security_id, status, probabilities, display_tier, is_primary, sampling_rule, valid_until, locked) select 'pred_bad_sum', run_id, target_row_id, security_id, 'pending_evaluation', '{"outperform":0.5,"flat":0.4,"underperform":0.2}', display_tier, false, sampling_rule, valid_until, locked from predictions where prediction_id = 'pred_test_1'$$, 'probabilities sum != 1');
select pg_temp.expect_fail($$insert into predictions (prediction_id, run_id, target_row_id, security_id, status, display_tier, is_primary, sampling_rule, valid_until, locked) select 'pred_bad_abstain', run_id, target_row_id, security_id, 'abstained', display_tier, false, sampling_rule, valid_until, locked from predictions where prediction_id = 'pred_test_1'$$, 'abstained without abstain_reason');
select pg_temp.expect_fail($$insert into predictions (prediction_id, run_id, target_row_id, security_id, status, display_tier, is_primary, sampling_rule, valid_until, locked) select 'pred_bad_primary', run_id, target_row_id, security_id, 'pending_evaluation', display_tier, true, 'scheduled_5m', valid_until, locked from predictions where prediction_id = 'pred_test_1'$$, 'scheduled_5m cannot be primary (D-23)');
select pg_temp.expect_fail($$insert into predictions (prediction_id, run_id, target_row_id, security_id, status, display_tier, is_primary, sampling_rule, valid_until, locked) select 'pred_bad_slot', run_id, target_row_id, security_id, 'pending_evaluation', display_tier, true, 'schedule_slot', valid_until, locked from predictions where prediction_id = 'pred_test_1'$$, 'schedule_slot without slot fields');
select pg_temp.expect_fail($$insert into predictions (prediction_id, run_id, target_row_id, security_id, status, display_tier, is_primary, sampling_rule, valid_until, locked) select 'pred_bad_locked', run_id, target_row_id, security_id, 'pending_evaluation', display_tier, false, sampling_rule, valid_until, '{"target_definition_version":"td-0.2"}' from predictions where prediction_id = 'pred_test_1'$$, 'locked missing version fields');
select pg_temp.expect_fail($$insert into benchmark_versions (benchmark_version_id, benchmark_id, version, effective_from, constituents, defined_at) values ('bmv_bad', 'bm_soxx_ref', 9, '2026-12-01', '[{"security_id":"sec_soxx","weight":0.9}]', '2026-11-30T00:00:00Z')$$, 'benchmark weights != 1');
select pg_temp.expect_fail($$insert into benchmark_versions (benchmark_version_id, benchmark_id, version, effective_from, constituents, defined_at) values ('bmv_late', 'bm_soxx_ref', 8, '2026-12-01', '[{"security_id":"sec_soxx","weight":1}]', '2026-12-02T00:00:00Z')$$, 'benchmark defined after it became effective');
select pg_temp.expect_fail($$insert into security_state_snapshots select (s).* from (select s from security_state_snapshots s where snapshot_id = 'snap_test_1') x$$, 'duplicate snapshot dedupe_key');

-- ---------- append-only tables ----------
select pg_temp.expect_fail($$update security_state_snapshots set explanation_summary = 'changed' where snapshot_id = 'snap_test_1'$$, 'update snapshot');
select pg_temp.expect_fail($$delete from reference_quotes where quote_id = 'rq_test_t0'$$, 'delete reference quote');

-- ---------- settlements: append-only, reporting flag switchable ----------
insert into prediction_settlements (settlement_id, prediction_id, settlement_version, start_quote_id, stock_return_pct,
  benchmark_return_pct, relative_return_pp, outcome_class, hit, brier, settled_at, is_reporting_version, reason_text)
values ('stl_test_v1', 'pred_test_1', 1, 'rq_test_t0', 0.42, 0.18, 0.24, 'outperform', true, 0.5798,
  '2026-12-01T16:21:00Z', true, 'synthetic test');
select pg_temp.expect_fail($$update prediction_settlements set brier = 0.1 where settlement_id = 'stl_test_v1'$$, 'rewrite settlement');
select pg_temp.expect_fail($$insert into prediction_settlements (settlement_id, prediction_id, settlement_version, settled_at, is_reporting_version, reason_text) values ('stl_test_v2', 'pred_test_1', 2, now(), true, 'x')$$, 'two reporting versions');
update prediction_settlements set is_reporting_version = false where settlement_id = 'stl_test_v1';
select pg_temp.expect_fail($$delete from prediction_settlements where settlement_id = 'stl_test_v1'$$, 'delete settlement');

-- ---------- RLS on everywhere ----------
do $$
declare n int;
begin
  select count(*) into n from pg_tables where schemaname = 'public' and not rowsecurity;
  if n <> 0 then raise exception 'RLS disabled on % public tables', n; end if;
  raise notice 'all assertions passed';
end $$;

rollback;
