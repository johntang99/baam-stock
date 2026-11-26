-- 0002_evidence_events · Phase 1 group 1 (DP 1.03–1.06), DATA_CONTRACT contract-0.7.2
-- Evidence documents + versions, events, links, milestones, analysis versions, LLM call log.
-- Columns/enums must match packages/contracts/schemas (services/py/tests/test_contracts.py).

create type evidence_verification_status as enum ('pending', 'media_report', 'primary_confirmed', 'conflicting', 'retracted');
create type arrival_mode as enum ('live', 'archived', 'simulated');
create type event_category as enum ('earnings_guidance', 'customer_demand', 'policy_export', 'executive_change', 'accounting_audit', 'product_supply', 'macro_rates', 'competition', 'litigation_regulatory', 'capital_estimates', 'trading_structure', 'm_and_a', 'investment_contract', 'license_policy');
create type event_progress_status as enum ('pending', 'outcome_confirmed', 'effective', 'terminated');
create type event_analysis_status as enum ('partial', 'complete', 'needs_review');
create type event_relation as enum ('subject', 'acquirer', 'target', 'supplier', 'customer', 'competitor', 'regulated_party', 'sector_wide');
create type milestone_type as enum ('agreement_signed', 'shareholder_vote', 'regulatory_filing', 'regulatory_clearance', 'closing', 'termination', 'complaint_filed', 'hearing', 'order', 'verdict', 'appeal', 'settlement', 'official_statement', 'proposed_rule', 'comment_period_end', 'rule_published', 'rule_effective', 'enforcement_action', 'license_applied', 'license_granted', 'license_denied', 'shipment_confirmed', 'board_announcement', 'guidance_update');
create type milestone_status as enum ('scheduled', 'occurred', 'delayed', 'cancelled');
create type analysis_kind as enum ('flash', 'full');
create type llm_purpose as enum ('extract_facts', 'draft_explanation');
create type llm_mode as enum ('live', 'replay');
create type llm_call_status as enum ('succeeded', 'rejected_validation', 'refused', 'failed');

-- ---------------------------------------------------------------- documents
create table source_documents (
  doc_id text primary key,
  source_id text not null references data_sources,
  canonical_url text,
  external_ref text,
  origin_doc_id text references source_documents,
  subject_company_ids text[] not null default '{}',
  unique (source_id, external_ref)
);

create table source_document_versions (
  doc_version_id text primary key,
  doc_id text not null references source_documents,
  version int not null check (version >= 1),
  content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  storage_path text,
  locator text,
  source_published_at timestamptz,
  source_published_precision time_precision,
  missing_reason text,
  received_at timestamptz not null,
  available_at timestamptz not null,
  arrival_mode arrival_mode not null,
  simulated_available_at timestamptz,
  is_correction_of text references source_document_versions,
  visibility visibility not null default 'public',
  unique (doc_id, version),
  unique (doc_id, content_hash),                                        -- duplicate delivery is idempotent (AC-07)
  check (source_published_at is not null or missing_reason is not null),  -- DC §1 null-reason rule (AC-06)
  check (source_published_at is null or source_published_precision is not null),
  check (available_at >= received_at),
  check ((arrival_mode = 'simulated') = (simulated_available_at is not null))
);

-- ---------------------------------------------------------------- events
create table events (
  event_id text primary key,
  category event_category not null,
  subtype text,
  identity_key text not null unique,
  progress_status event_progress_status not null default 'pending',
  evidence_status evidence_verification_status not null default 'pending',
  analysis_status event_analysis_status not null default 'partial',
  current_analysis_version int check (current_analysis_version >= 1),
  row_version int not null default 1 check (row_version >= 1),
  first_seen_at timestamptz not null
);

create table event_evidence (
  evidence_id text primary key,
  event_id text not null references events,
  doc_version_id text not null references source_document_versions,
  claim text not null,
  claimant text,
  span jsonb not null,
  verification_status evidence_verification_status not null,
  available_at timestamptz not null,
  visibility visibility not null default 'public',
  independent_origin_key text not null,
  unique (event_id, doc_version_id, claim)
);

create table event_security_links (
  event_id text not null references events,
  security_id text not null references securities,
  relation event_relation not null,
  exposure_note text,
  primary key (event_id, security_id)
);

create table event_milestones (
  milestone_id text primary key,
  event_id text not null references events,
  milestone_type milestone_type not null,
  decision_body text,
  expected_at timestamptz,
  actual_at timestamptz,
  status milestone_status not null default 'scheduled',
  evidence_ids text[] not null default '{}',
  check (status <> 'occurred' or actual_at is not null)
);

create table event_analysis_versions (
  analysis_id text primary key check (analysis_id ~ '^eav_'),
  event_id text not null references events,
  security_id text not null references securities,
  analysis_version int not null check (analysis_version >= 1),
  analysis_kind analysis_kind not null,
  analysis_as_of timestamptz not null,
  published_at timestamptz,
  evidence_ids text[],
  facts jsonb,
  expectation_comparison jsonb,
  missing_reason text,
  impact jsonb,
  priority jsonb,
  market_reaction jsonb,
  market_explanation jsonb not null,
  reasoning_trace jsonb,
  historical_cases jsonb,
  scenarios jsonb,
  data_gaps text[],
  rule_version text,
  model_versions jsonb,
  prediction_readiness jsonb not null,
  supersedes_analysis_id text references event_analysis_versions,
  unique (event_id, security_id, analysis_version),
  check (published_at is null or published_at >= analysis_as_of),
  check (analysis_version = 1 or supersedes_analysis_id is not null)
);

-- ---------------------------------------------------------------- LLM call log
create table llm_calls (
  call_id text primary key check (call_id ~ '^llm_'),
  purpose llm_purpose not null,
  provider text not null,
  model text not null,
  prompt_version text not null,
  prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
  input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
  output_hash text check (output_hash ~ '^[0-9a-f]{64}$'),
  doc_version_id text references source_document_versions,
  mode llm_mode not null,
  request_params jsonb not null,
  usage jsonb not null default '{}'::jsonb,
  stop_reason text,
  status llm_call_status not null,
  error jsonb,
  latency_ms int check (latency_ms >= 0),
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- links from 0001 tables
alter table collection_items add foreign key (doc_version_id) references source_document_versions;
alter table collection_items add foreign key (linked_event_id) references events;
alter table predictions add foreign key (event_id) references events;
alter table prediction_targets add foreign key (event_id) references events;

create index source_document_versions_available_idx on source_document_versions (available_at);
create index event_evidence_event_idx on event_evidence (event_id);
create index event_analysis_versions_lookup_idx on event_analysis_versions (event_id, security_id, analysis_version desc);

-- ---------------------------------------------------------------- append-only rules
-- document versions: only `visibility` may change (compliance review can release or restrict); never delete
create function source_document_versions_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'IMMUTABLE: source document versions are append-only' using errcode = 'P0001';
  end if;
  if (to_jsonb(new) - 'visibility') is distinct from (to_jsonb(old) - 'visibility') then
    raise exception 'IMMUTABLE: document version % is append-only; corrections create a new version', old.doc_version_id
      using errcode = 'P0001';
  end if;
  return new;
end $$;
create trigger source_document_versions_guard before update or delete on source_document_versions
  for each row execute function source_document_versions_guard();

create function event_evidence_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'IMMUTABLE: evidence is append-only; retract with verification_status' using errcode = 'P0001';
  end if;
  if (to_jsonb(new) - 'visibility' - 'verification_status') is distinct from
     (to_jsonb(old) - 'visibility' - 'verification_status') then
    raise exception 'IMMUTABLE: evidence % content is append-only', old.evidence_id using errcode = 'P0001';
  end if;
  return new;
end $$;
create trigger event_evidence_guard before update or delete on event_evidence
  for each row execute function event_evidence_guard();

create trigger event_analysis_versions_append_only before update or delete on event_analysis_versions
  for each row execute function forbid_mutation();
create trigger llm_calls_append_only before update or delete on llm_calls
  for each row execute function forbid_mutation();

-- events: parent with optimistic lock; row_version must increase by exactly 1 on every update (DC §1 乐观锁)
create function events_row_version_guard() returns trigger
language plpgsql as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'IMMUTABLE: events cannot be deleted; use progress_status=terminated' using errcode = 'P0001';
  end if;
  if new.row_version <> old.row_version + 1 then
    raise exception 'CONFLICT_STALE_VERSION: event % row_version % -> % (must increment by 1)',
      old.event_id, old.row_version, new.row_version using errcode = 'P0001';
  end if;
  if new.identity_key is distinct from old.identity_key then
    raise exception 'IMMUTABLE: identity_key of % cannot change', old.event_id using errcode = 'P0001';
  end if;
  if old.current_analysis_version is not null and
     (new.current_analysis_version is null or new.current_analysis_version < old.current_analysis_version) then
    raise exception 'CONFLICT_STALE_VERSION: current_analysis_version cannot move backwards' using errcode = 'P0001';
  end if;
  return new;
end $$;
create trigger events_row_version_guard before update or delete on events
  for each row execute function events_row_version_guard();

-- RLS on for the new tables (deny-by-default, DC §10 policies arrive in Phase 2)
alter table source_documents enable row level security;
alter table source_document_versions enable row level security;
alter table events enable row level security;
alter table event_evidence enable row level security;
alter table event_security_links enable row level security;
alter table event_milestones enable row level security;
alter table event_analysis_versions enable row level security;
alter table llm_calls enable row level security;

-- latest analysis per (event, security); events.current_analysis_version is only a monotonic change counter
-- across securities (OPEN_QUESTIONS OQ-24)
create view event_analysis_current as
  select distinct on (event_id, security_id) *
  from event_analysis_versions
  order by event_id, security_id, analysis_version desc;
