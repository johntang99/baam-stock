/* AUTO-GENERATED from packages/contracts/schemas by scripts/gen-ts.mjs. Do not edit. */
export type SchemaVersion = "contract-0.7.4"
/**
 * UTC ISO-8601 with Z suffix (DC §1)
 */

export type Timestamp = string

/**
 * DC §3.10
 */

export interface Alerts {
schema_version?: SchemaVersion
alert_id: string
severity: ("info" | "warning" | "critical")
kind: ("source_down" | "source_latency" | "quote_stale" | "pipeline_failed" | "settlement_backlog" | "drift" | "gate_regression" | "onboarding_blocked")
ref?: (string | null)
opened_at: Timestamp
acknowledged_by?: (string | null)
resolved_at?: (Timestamp | null)
message: string
}

export interface BenchmarkDefinitions {
schema_version?: SchemaVersion
benchmark_id: string
kind: ("peer_basket" | "etf_reference")
target_security_id?: (string | null)
methodology: string
missing_rule: string
}

export type IsoDate = string
/**
 * UTC ISO-8601 with Z suffix (DC §1)
 */

export interface BenchmarkVersions {
schema_version?: SchemaVersion
benchmark_version_id: string
benchmark_id: string
version: number
effective_from: IsoDate
effective_to?: (IsoDate | null)
/**
 * weights sum to 1
 */
constituents: Constituent[]
sync_tolerance_ms: number
defined_at: Timestamp
}

export interface Constituent {
security_id: string
weight: number
}

export type CollectionChannel = ("filing" | "insider_filing" | "company_ir" | "news_wire" | "policy" | "court" | "macro" | "expectation" | "market_data" | "peer_company" | "user_submission")

export type CollectionCategory = ("earnings_guidance" | "policy_export" | "customer_demand" | "supply_chain" | "m_and_a" | "litigation" | "management" | "product" | "capital_return" | "macro" | "analyst_rating" | "insider_trade" | "market_data" | "other")
/**
 * UTC ISO-8601 with Z suffix (DC §1)
 */

export type TimePrecision = ("ms" | "s" | "minute" | "hour" | "day" | "unknown")

/**
 * DC §3.2: one row per retrieved item, including those not used (append-only)
 */

export interface CollectionItems {
schema_version?: SchemaVersion
item_id: string
collection_run_id: string
source_id: string
channel: CollectionChannel
submission_id?: (string | null)
submitted_by?: (string | null)
category: CollectionCategory
category_confidence?: (number | null)
title: string
snippet?: (string | null)
doc_version_id?: (string | null)
mentions: string[]
disposition: ("kept" | "duplicate" | "excluded_irrelevant" | "excluded_after_asof" | "excluded_restricted" | "pending_review" | "fetch_failed")
duplicate_of?: (string | null)
exclusion_reason?: (string | null)
relevance?: (number | null)
linked_event_id?: (string | null)
linked_evidence_ids: string[]
occurred_at?: (Timestamp | null)
source_published_at?: (Timestamp | null)
source_published_precision?: (TimePrecision | null)
received_at?: (Timestamp | null)
available_at?: (Timestamp | null)
}

export interface CollectionRuns {
schema_version?: SchemaVersion
collection_run_id: string
pipeline_run_id?: (string | null)
snapshot_id?: (string | null)
security_id: string
window_from: Timestamp
window_to: Timestamp
sources_polled: {
source_id: string
channel: CollectionChannel
status: ("ok" | "timeout" | "error" | "skipped")
items_fetched: number
latency_ms?: (number | null)
}[]
/**
 * aggregated from collection_items, never hand-filled
 */
counts: {
fetched?: number
kept?: number
duplicate?: number
excluded?: number
pending_review?: number
failed?: number
by_channel?: {

}
by_category?: {

}
}
started_at: Timestamp
finished_at?: (Timestamp | null)
}

export interface Companies {
schema_version?: SchemaVersion
company_id: string
legal_name: string
cik?: (string | null)
sector: string
industry: string
/**
 * { "fy_end_month": 1, "week_based": true }
 */
fiscal_calendar: {

}
row_version: number
}

export type IndustryTemplate = ("semiconductor" | "bank" | "biotech" | "generic")

/**
 * DC §3.1; UQ (company_id, version)
 */

export interface CompanyProfileVersions {
schema_version?: SchemaVersion
profile_version_id: string
company_id: string
version: number
effective_from: Timestamp
key_metrics: string[]
exposures: {

}
official_sources: {

}
priority_rules_version: string
industry_template: IndustryTemplate
valuation_peers: string[]
}

export interface CorporateActions {
schema_version?: SchemaVersion
action_id: string
security_id: string
action_type: ("split" | "reverse_split" | "cash_dividend" | "special_dividend" | "spin_off" | "ticker_change" | "merger_delisting")
announced_at: Timestamp
ex_date: IsoDate
effective_at?: (Timestamp | null)
ratio?: (number | null)
cash_amount?: (number | null)
source_id: string
available_at: Timestamp
}

export interface DataSourceHealth {
schema_version?: SchemaVersion
source_id: string
checked_at: Timestamp
status: ("healthy" | "degraded" | "down")
latency_p50_ms?: (number | null)
latency_p95_ms?: (number | null)
last_success_at?: (Timestamp | null)
error_rate_1h?: (number | null)
license_scope: ("public" | "licensed_internal" | "licensed_display" | "restricted")
verification_status: ("proposed" | "sample_verified" | "contracted" | "retired")
note?: (string | null)
}

export interface DataSources {
schema_version?: SchemaVersion
source_id: string
kind: ("market_data" | "filing" | "insider_filing" | "company_ir" | "news" | "policy" | "court" | "expectation" | "macro" | "options" | "llm")
provider: string
license_scope: ("public" | "licensed_internal" | "licensed_display" | "restricted")
verification_status: ("proposed" | "sample_verified" | "contracted" | "retired")
time_precision_default: TimePrecision
notes?: (string | null)
}

export interface DocketEntries {
schema_version?: SchemaVersion
docket_entry_id: string
event_id?: (string | null)
court: string
case_number: string
entry_no: number
entry_type: ("complaint" | "motion" | "order" | "opinion" | "judgment" | "verdict" | "appeal_notice" | "settlement" | "other")
filed_at: Timestamp
entered_at?: (Timestamp | null)
title: string
doc_version_id?: (string | null)
source_id: string
available_at: Timestamp
}

export type ExplanationStatus = ("supported" | "partial" | "insufficient")

/**
 * DC §3.4 (table since contract-0.7.2, migration 0002); UQ (event_id, security_id, analysis_version)
 */

export interface EventAnalysisVersions {
schema_version?: SchemaVersion
analysis_id: string
event_id: string
security_id: string
analysis_version: number
analysis_kind: ("flash" | "full")
analysis_as_of: Timestamp
published_at?: (Timestamp | null)
evidence_ids?: string[]
facts?: {

}[]
expectation_comparison?: ({

} | null)
missing_reason?: (string | null)
impact?: {

}[]
priority?: {

}
market_reaction?: {
ref_before_quote_id?: (string | null)
ref_asof_quote_id?: (string | null)
stock_return_pct?: (number | null)
benchmark_return_pct?: (number | null)
relative_return_pp?: (number | null)
missing_reason?: (string | null)
}
market_explanation: {
status: ExplanationStatus
observed_facts: Statement[]
possible_drivers: Statement[]
counter_evidence: Statement[]
unexplained: (Statement | string)[]
concurrent_events?: (Statement | string)[]
valuation_context?: ({

} | null)
}
reasoning_trace?: {
step: number
kind: ("market_fact" | "timing_check" | "evidence_fact" | "attribution" | "counter_check" | "analogue" | "gap" | "conclusion")
inputs: {

}
rule?: (string | null)
conclusion: string
confidence?: (("high" | "medium" | "low") | null)
}[]
historical_cases?: ({

} | null)
scenarios?: ({

}[] | null)
data_gaps?: string[]
rule_version?: string
model_versions?: {

}
prediction_readiness: PredictionReadiness
supersedes_analysis_id?: (string | null)
}
/**
 * market_explanation statement (D-46): must cite >=1 evidence or quote for observed_facts/possible_drivers/counter_evidence
 */

export interface Statement {
text: string
evidence_ids: string[]
quote_ids: string[]
item_ids: string[]
trace_step?: (number | null)
}
/**
 * DC §3.5
 */

export interface PredictionReadiness {
event_outcome: ReadinessItem
stock_reaction: ReadinessItem
}

export interface ReadinessItem {
status: ("ready" | "missing_inputs" | "manual_review" | "not_applicable")
reason: string
analysis_id?: string
allowed_models?: string[]
}

export type EvidenceVerificationStatus = ("pending" | "media_report" | "primary_confirmed" | "conflicting" | "retracted")
/**
 * UTC ISO-8601 with Z suffix (DC §1)
 */

export type Visibility = ("public" | "internal" | "restricted_review")

/**
 * DC §3.2 (table since contract-0.7.2, migration 0002)
 */

export interface EventEvidence {
schema_version?: SchemaVersion
evidence_id: string
event_id: string
doc_version_id: string
claim: string
claimant?: (string | null)
/**
 * page/paragraph/char range
 */
span: {

}
verification_status: EvidenceVerificationStatus
available_at: Timestamp
visibility: Visibility
independent_origin_key: string
}

export interface EventMilestones {
schema_version?: SchemaVersion
milestone_id: string
event_id: string
milestone_type: ("agreement_signed" | "shareholder_vote" | "regulatory_filing" | "regulatory_clearance" | "closing" | "termination" | "complaint_filed" | "hearing" | "order" | "verdict" | "appeal" | "settlement" | "official_statement" | "proposed_rule" | "comment_period_end" | "rule_published" | "rule_effective" | "enforcement_action" | "license_applied" | "license_granted" | "license_denied" | "shipment_confirmed" | "board_announcement" | "guidance_update")
decision_body?: (string | null)
expected_at?: (Timestamp | null)
actual_at?: (Timestamp | null)
status: ("scheduled" | "occurred" | "delayed" | "cancelled")
evidence_ids: string[]
}

export interface EventSecurityLinks {
schema_version?: SchemaVersion
event_id: string
security_id: string
relation: ("subject" | "acquirer" | "target" | "supplier" | "customer" | "competitor" | "regulated_party" | "sector_wide")
exposure_note?: (string | null)
}

export type EventCategory = ("earnings_guidance" | "customer_demand" | "policy_export" | "executive_change" | "accounting_audit" | "product_supply" | "macro_rates" | "competition" | "litigation_regulatory" | "capital_estimates" | "trading_structure" | "m_and_a" | "investment_contract" | "license_policy")

export interface Events {
schema_version?: SchemaVersion
event_id: string
category: EventCategory
subtype?: (string | null)
identity_key: string
progress_status: ("pending" | "outcome_confirmed" | "effective" | "terminated")
evidence_status: EvidenceVerificationStatus
analysis_status: ("partial" | "complete" | "needs_review")
current_analysis_version?: (number | null)
row_version: number
first_seen_at: Timestamp
}

export interface ExpectationSnapshots {
schema_version?: SchemaVersion
exp_id: string
company_id: string
metric: string
fiscal_period: string
value?: (number | null)
range_low?: (number | null)
range_high?: (number | null)
unit: string
accounting_basis: ("gaap" | "non_gaap" | "company_defined")
expectation_type: ("company_guidance" | "analyst_consensus" | "other_public")
snapshot_as_of: Timestamp
snapshot_precision: TimePrecision
available_at: Timestamp
source_id: string
revision_of_exp_id?: (string | null)
}

export interface ExtractionEvalRuns {
schema_version?: SchemaVersion
eval_run_id: string
label_set_version: string
llm_provider: string
llm_model: string
prompt_version: string
field_group: ("numeric_fact" | "direction" | "scope" | "certainty")
precision: number
recall: number
f1: number
n_docs: number
passed: boolean
created_at: Timestamp
}

export type TargetId = ("regular_60m" | "regular_60m_move" | "regular_to_close" | "next_regular_session" | "overnight_gap" | "event_outcome")
/**
 * UTC ISO-8601 with Z suffix (DC §1)
 */

export interface ForecastAccuracyRollups {
schema_version?: SchemaVersion
security_id: string
target_id: TargetId
group_key: string
window: ("session" | "rolling_20d" | "rolling_60d" | "since_live")
n_published: number
n_settled: number
n_abstained: number
n_unsettleable: number
hit_rate?: (number | null)
brier?: (number | null)
bss_class_frequency?: (number | null)
coverage_p80?: (number | null)
coverage_p90?: (number | null)
mean_interval_width_pp?: (number | null)
mean_residual_pp?: (number | null)
mean_abs_residual_pp?: (number | null)
calibration_bins: {

}[]
model_version_ids: string[]
computed_at: Timestamp
}

export interface ForecastSchedules {
schema_version?: SchemaVersion
schedule_id: string
schedule_version: string
effective_from: IsoDate
effective_to?: (IsoDate | null)
slots: {
slot_id: string
time_et: string
kind: ("pre_open_outlook" | "intraday" | "post_close_outlook")
target_ids: TargetId[]
start_rule: string
}[]
half_day_rule: {

}
holiday_rule: string
miss_rule: {
grace_s: number
on_miss: string
}
}

export type PredictionStatus = ("pending_evaluation" | "published" | "awaiting_trigger" | "awaiting_settlement" | "settled" | "abstained" | "not_triggered" | "unsettleable")

/**
 * DC §3.7a (table since contract-0.7.4, migration 0006; derived, rebuilt after settlement)
 */

export interface ForecastVsActual {
schema_version?: SchemaVersion
prediction_id: string
security_id: string
session_date: IsoDate
target_id: TargetId
schedule_slot_id?: (string | null)
t0_at?: (Timestamp | null)
target_end_at?: (Timestamp | null)
forecast_path: {

}
actual_path: {

}[]
status: PredictionStatus
outcome_class?: (string | null)
hit?: (boolean | null)
brier?: (number | null)
inside_p80?: (boolean | null)
inside_p90?: (boolean | null)
residual_pp?: (number | null)
abs_move_error_pp?: (number | null)
}

export interface IndustryTemplates {
schema_version?: SchemaVersion
template_id: IndustryTemplate
version: number
key_metrics_default: string[]
event_types_enabled: string[]
official_sources_default: {

}
exposure_dimensions: string[]
}

export interface InsiderTransactions {
schema_version?: SchemaVersion
txn_id: string
security_id: string
insider_name: string
insider_role: string
transaction_code: string
is_10b5_1?: (boolean | null)
shares: number
price?: (number | null)
transaction_date: IsoDate
filed_at: Timestamp
accession_no: string
available_at: Timestamp
}

export interface Jobs {
schema_version?: SchemaVersion
job_id: string
job_type: ("ingest_doc" | "analyze_event" | "build_snapshot" | "run_forecast" | "settle_due" | "replay_day" | "build_dataset" | "train" | "evaluate" | "shadow_score" | "pipeline_step" | "onboarding_step" | "source_healthcheck")
pipeline_run_id?: (string | null)
onboarding_id?: (string | null)
payload: {

}
idempotency_key: string
status: ("queued" | "running" | "succeeded" | "failed" | "retry_wait" | "dead")
attempts: number
max_attempts: number
run_after: Timestamp
locked_by?: (string | null)
locked_at?: (Timestamp | null)
last_error?: (string | null)
}

export interface LlmCalls {
schema_version?: SchemaVersion
call_id: string
purpose: ("extract_facts" | "draft_explanation")
provider: string
model: string
prompt_version: string
prompt_hash: string
input_hash: string
output_hash?: (string | null)
doc_version_id?: (string | null)
mode: ("live" | "replay")
/**
 * effort, max_tokens, output schema id; tools must be [] (no web search)
 */
request_params: {

}
/**
 * input_tokens, output_tokens, cache_* as returned
 */
usage: {

}
stop_reason?: (string | null)
status: ("succeeded" | "rejected_validation" | "refused" | "failed")
error?: (Error | null)
latency_ms?: (number | null)
created_at: Timestamp
}

export interface Error {
code: string
message: string
details?: {

}
}

export interface MacroReleases {
schema_version?: SchemaVersion
release_id: string
series_id: string
reference_period: string
vintage_date: IsoDate
value: number
is_first_release: boolean
release_at: Timestamp
consensus_value?: (number | null)
source_id: string
available_at: Timestamp
}

export type SessionType = ("pre_market" | "regular" | "post_market")

/**
 * DC §3.3 (schema only in P0; table in Phase 1)
 */

export interface MarketBars_1M {
schema_version?: SchemaVersion
security_id: string
bar_start: Timestamp
open: number
high: number
low: number
close: number
volume: number
vwap?: (number | null)
trade_count?: (number | null)
session_type: SessionType
bar_version: number
}

export type Audience = ("internal" | "selected_v1" | "selected_v2" | "selected_v3")

/**
 * DC §3.8 (schema only in P0)
 */

export interface ModelDeployments {
schema_version?: SchemaVersion
deployment_id: string
target_id: TargetId
scope: {

}
from_model_version_id?: (string | null)
to_model_version_id: string
approved_by: string
approval_note: string
effective_at: Timestamp
audience: Audience
slices?: ({

} | null)
state: ("active" | "rolled_back" | "superseded")
rollback_reason?: (string | null)
}

export interface ModelEvaluations {
schema_version?: SchemaVersion
evaluation_id: string
candidate_model_version_id: string
comparator_model_version_id: string
eval_subset: string
common_coverage: {
n_eligible: number
n_candidate: number
n_comparator: number
n_common: number
}
metrics: {

}
n_independent_days: number
n_event_clusters: number
gate_config_version: string
gate_result: ("pass" | "fail" | "inconclusive")
failed_conditions: string[]
}

export type ModelFamily = ("class_frequency" | "always_flat" | "persistence" | "har_vol" | "market_logit" | "market_event_logit" | "gbdt" | "two_stage")

export type ParamLayers = ("market" | "market_sector" | "market_sector_company")

/**
 * DC §3.8 (table since contract-0.7.3, migration 0004)
 */

export interface ModelVersions {
schema_version?: SchemaVersion
model_version_id: string
training_run_id: string
target_id: TargetId
model_family: ModelFamily
param_layers: ParamLayers
scope?: {

}
features?: string[]
hyperparams?: {

}
coefficients_path?: string
calibration_version?: string
publish_threshold?: {

}
artifact_sha256?: string
status: ("candidate" | "shadow" | "pending_approval" | "live" | "retired" | "rejected" | "rolled_back")
}

export type Exchange = ("XNAS" | "XNYS" | "ARCX" | "XCBO")

/**
 * DC §3.10
 */

export interface OnboardingRequests {
schema_version?: SchemaVersion
onboarding_id: string
ticker: string
cik?: (string | null)
primary_exchange?: (Exchange | null)
requested_by: string
approved_by?: (string | null)
target_tier: ("pilot" | "batch2" | "peer_only" | "reference")
stage: ("draft" | "profile_review" | "sources_configured" | "backfilling" | "data_validated" | "training" | "shadow" | "active" | "blocked" | "rejected" | "paused")
checklist: {
item: string
status: ("todo" | "done" | "failed" | "waived")
evidence?: (string | null)
}[]
backfill_report?: ({

} | null)
param_policy: ("market_sector_only" | "company_offset_candidate")
profile_version_id?: (string | null)
benchmark_version_id?: (string | null)
dataset_version_id?: (string | null)
model_version_id?: (string | null)
blocked_reason?: (string | null)
}

export interface OptionsSnapshots {
schema_version?: SchemaVersion
opt_snap_id: string
security_id: string
snapshot_at: Timestamp
expiry: IsoDate
atm_iv?: (number | null)
iv_25d_put?: (number | null)
iv_25d_call?: (number | null)
implied_move_pct?: (number | null)
put_call_volume_ratio?: (number | null)
source_id: string
available_at: Timestamp
}

export interface PipelineRunSteps {
schema_version?: SchemaVersion
pipeline_run_id: string
step_no: number
step: ("collect_evidence" | "verify_dedupe" | "analyze_events" | "build_snapshot" | "readiness_check" | "infer" | "publish" | "schedule_settlement")
security_id: string
status: ("pending" | "running" | "succeeded" | "skipped" | "failed" | "retry_wait")
attempt: number
started_at?: (Timestamp | null)
finished_at?: (Timestamp | null)
detail: {

}
error?: (Error | null)
job_id?: (string | null)
}

export interface PipelineRuns {
schema_version?: SchemaVersion
pipeline_run_id: string
security_ids: string[]
target_ids: TargetId[]
trigger_type: ("on_demand" | "scheduled" | "event" | "market_move" | "user_supplement")
requested_by?: (string | null)
mode: ("live" | "replay" | "dry_run" | "supplement")
base_run_id?: (string | null)
submission_ids: string[]
as_of: Timestamp
status: ("queued" | "running" | "succeeded" | "partial" | "failed" | "cancelled")
reuse_policy: ("reuse_if_unchanged" | "force_recompute")
outputs: {

}
started_at?: (Timestamp | null)
finished_at?: (Timestamp | null)
sla_ms: number
idempotency_key: string
}

export type TriggerType = ("scheduled" | "event" | "market_move" | "on_demand" | "session_check" | "user_supplement")
/**
 * UTC ISO-8601 with Z suffix (DC §1)
 */

export interface PredictionRuns {
schema_version?: SchemaVersion
run_id: string
trigger_type: TriggerType
trigger_ref?: (string | null)
snapshot_id: string
event_analysis_ids: string[]
feature_snapshot_id: string
model_version_id: string
calibration_version: string
baseline_model_version_id: string
evidence_gaps: string[]
publish_deadline: Timestamp
published_at?: (Timestamp | null)
idempotency_key: string
}

export type InvalidReason = ("no_sync_start_quote" | "no_sync_end_quote" | "halted" | "benchmark_unavailable" | "corporate_action" | "source_unverifiable")

/**
 * DC §3.7; UQ (prediction_id, settlement_version)
 */

export interface PredictionSettlements {
schema_version?: SchemaVersion
settlement_id: string
prediction_id: string
settlement_version: number
start_quote_id?: (string | null)
end_quote_id?: (string | null)
benchmark_start_quote_ids: string[]
benchmark_end_quote_ids: string[]
stock_return_pct?: (number | null)
benchmark_return_pct?: (number | null)
relative_return_pp?: (number | null)
outcome_class?: (string | null)
hit?: (boolean | null)
brier?: (number | null)
abs_relative_move_pp?: (number | null)
pinball_loss?: ({

} | null)
quantile_hits?: ({

} | null)
event_outcome?: (string | null)
settlement_evidence_ids: string[]
public_confirmation_at?: (Timestamp | null)
legal_effective_at?: (Timestamp | null)
triggered?: (boolean | null)
triggered_at?: (Timestamp | null)
invalid_reason?: (InvalidReason | null)
settled_at: Timestamp
is_reporting_version: boolean
reason_text: string
}

export interface PredictionTargets {
schema_version?: SchemaVersion
target_row_id: string
target_id: TargetId
target_definition_version: string
track: ("stock_reaction" | "event_outcome" | "conditional_scenario")
classes: string[]
threshold_rule?: ({
type: "vol_scaled"
k: number
sigma_model: string
on_missing_sigma: "abstain"
} | null)
output_kind: ("class_probs" | "quantiles" | "scenarios")
window_rule: {

}
min_remaining_min?: (number | null)
event_id?: (string | null)
question?: (string | null)
deadline_at?: (Timestamp | null)
deadline_tz?: (string | null)
confirm_sources?: (string[] | null)
outcome_resolution?: ({

} | null)
no_result_rule?: (string | null)
condition?: ({

} | null)
invalid_rules_version: string
}

export type DisplayTier = ("validated_public" | "internal_shadow" | "scenario_only")

export type AbstainReason = ("insufficient_data" | "stale_quote" | "halted" | "benchmark_unavailable" | "conflicting_facts" | "window_insufficient" | "market_closed" | "model_not_validated" | "manual_review" | "low_edge" | "slot_missed")

export type SamplingRule = ("user_supplement" | "schedule_slot" | "scheduled_5m" | "event_first" | "market_move_first" | "on_demand" | "revision")
/**
 * UTC ISO-8601 with Z suffix (DC §1)
 */

export interface Predictions {
schema_version?: SchemaVersion
prediction_id: string
run_id: string
target_row_id: string
security_id: string
event_id?: (string | null)
status: PredictionStatus
probabilities?: (Probabilities | null)
predicted_class?: (string | null)
interval?: ({
quantiles: {

}
unit: string
validated: boolean
} | null)
sigma_hat_pp?: (number | null)
threshold_pp?: (number | null)
move_quantiles?: ({
p50: number
p80: number
p90: number
unit: "abs_relative_pp"
} | null)
scenarios?: ({
outcome: string
label: string
evidence_direction?: (string | null)
}[] | null)
edge_vs_baseline?: (number | null)
display_tier: DisplayTier
abstain_reason?: (AbstainReason | null)
is_primary: boolean
sampling_rule: SamplingRule
schedule_slot_id?: (string | null)
schedule_version?: (string | null)
scheduled_for?: (Timestamp | null)
supersedes_prediction_id?: (string | null)
valid_until: Timestamp
/**
 * frozen at publish; immutable after published (DB trigger)
 */
locked: {
target_definition_version: string
quote_rule_version: string
benchmark_version_id: string
calendar_version: string
model_version_id: string
calibration_version: (string | null)
schema_version: string
sigma_model_version: (string | null)
sigma_hat_pp: (number | null)
threshold_k: (number | null)
threshold_pp: (number | null)
feature_set_version: string
}
t0_quote_id?: (string | null)
t0_benchmark_quote_ids: string[]
target_end_at?: (Timestamp | null)
published_at?: (Timestamp | null)
}
/**
 * keys = class enum; sum = 1 ± 1e-6 (checked by validator, not expressible in JSON Schema)
 */

export interface Probabilities {
[k: string]: number
}

export interface ReferenceQuotes {
schema_version?: SchemaVersion
quote_id: string
security_id: string
quote_ts: Timestamp
received_at: Timestamp
session_type: SessionType
bid?: (number | null)
ask?: (number | null)
mid?: (number | null)
last?: (number | null)
spread_bp?: (number | null)
price_type: ("nbbo_mid" | "official_close" | "official_open" | "last_trade")
quality_flags: ("stale" | "wide_spread" | "halted" | "luld_pause" | "crossed" | "delayed")[]
is_qualifying: boolean
quote_rule_version: string
vendor_source_id: string
adjustment_basis: string
}

export type CoverageTier = ("pilot" | "batch2" | "peer_only" | "reference" | "inactive")

/**
 * DC §3.1
 */

export interface Securities {
schema_version?: SchemaVersion
security_id: string
company_id: string
/**
 * etf/index added in contract-0.7.1 (reference instruments, D-31)
 */
security_type: ("common" | "adr" | "etf" | "index")
primary_exchange: Exchange
currency: string
coverage_tier: CoverageTier
primary_benchmark_id?: (string | null)
reference_benchmark_id?: (string | null)
}

export interface SecurityIdentifiers {
schema_version?: SchemaVersion
security_id: string
id_type: string
value: string
valid_from: IsoDate
valid_to?: (IsoDate | null)
}

export type MarketState = ("pre_market" | "regular" | "post_market" | "closed" | "halted")

export interface SecurityStateSnapshots {
schema_version?: SchemaVersion
snapshot_id: string
security_id: string
trigger_type: TriggerType
trigger_ref?: (string | null)
analysis_as_of: Timestamp
evidence_watermark: Timestamp
market_watermark: Timestamp
market_state: MarketState
session_date: IsoDate
last_quote_id?: (string | null)
benchmark_version_id: string
day_return_pct?: (number | null)
day_relative_pp?: (number | null)
event_analysis_ids: string[]
new_catalyst_found: boolean
explanation_status: ExplanationStatus
explanation_summary: string
data_quality: ("ok" | "stale" | "partial" | "failed")
run_state: ("running" | "complete" | "degraded" | "failed")
quality_issues: {

}[]
last_valid_at?: (Timestamp | null)
valid_until: Timestamp
prediction_readiness: PredictionReadiness
dedupe_key: string
published_at: Timestamp
}
/**
 * DC §3.5
 */

export interface SourceDocumentVersions {
schema_version?: SchemaVersion
doc_version_id: string
doc_id: string
version: number
content_hash: string
storage_path?: (string | null)
locator?: (string | null)
source_published_at?: (Timestamp | null)
source_published_precision?: (TimePrecision | null)
missing_reason?: (string | null)
received_at: Timestamp
available_at: Timestamp
arrival_mode: ("live" | "archived" | "simulated")
simulated_available_at?: (Timestamp | null)
is_correction_of?: (string | null)
visibility: Visibility
}

export interface SourceDocuments {
schema_version?: SchemaVersion
doc_id: string
source_id: string
canonical_url?: (string | null)
external_ref?: (string | null)
origin_doc_id?: (string | null)
subject_company_ids: string[]
}

export interface TradingSessions {
schema_version?: SchemaVersion
exchange: Exchange
session_date: IsoDate
status: ("open" | "early_close" | "closed")
open_at?: (Timestamp | null)
close_at?: (Timestamp | null)
source: string
calendar_version: string
}

export interface TrainingDatasetVersions {
schema_version?: SchemaVersion
dataset_version_id: string
target_id: TargetId
feature_set_version: string
label_version: string
source_versions: {

}
time_range: {
start: IsoDate
end: IsoDate
}
splits: {
name: ("train" | "calibration" | "validation" | "holdout")
start: IsoDate
end: IsoDate
embargo_days: number
}[]
availability_check_passed: boolean
n_rows: number
n_trading_days: number
n_event_clusters: number
class_balance: {

}
exclusions: {

}
parent_dataset_version_id?: (string | null)
manifest_path: string
created_at: Timestamp
}

export interface TrainingRunMetrics {
schema_version?: SchemaVersion
training_run_id: string
seq: number
stage: string
iteration?: (number | null)
subset: ("train" | "calibration" | "validation" | "holdout" | "shadow")
target_id: TargetId
group_key: string
metric: ("log_loss" | "brier" | "brier_skill_score" | "hit_rate" | "coverage" | "ece" | "n_effective" | "pinball_loss" | "interval_coverage" | "interval_width" | "trigger_rate")
reference_model?: (("class_frequency" | "always_flat" | "persistence" | "har_vol") | null)
ci95_low?: (number | null)
ci95_high?: (number | null)
value: number
denominator?: (number | null)
recorded_at: Timestamp
}

export interface TrainingRuns {
schema_version?: SchemaVersion
training_run_id: string
dataset_version_id: string
trigger: ("scheduled_weekly" | "manual" | "drift")
parent_model_version_id?: (string | null)
code_version: string
config_hash: string
random_seed: number
status: ("queued" | "building_dataset" | "training" | "calibrating" | "evaluating" | "completed" | "failed" | "cancelled")
stage?: (string | null)
started_at?: (Timestamp | null)
finished_at?: (Timestamp | null)
error?: (Error | null)
artifact_paths: {

}
idempotency_key: string
}

export interface UserSubmissions {
schema_version?: SchemaVersion
submission_id: string
submitted_by: string
security_ids: string[]
input_kind: ("link" | "text" | "file")
url?: (string | null)
text?: (string | null)
file_path?: (string | null)
user_note?: (string | null)
user_categories: string[]
system_categories: {
category: CollectionCategory
confidence: number
}[]
final_categories: string[]
submitted_at: Timestamp
status: ("received" | "fetching" | "verifying" | "verified_primary" | "media_level" | "unverified" | "duplicate" | "rejected_restricted" | "fetch_failed")
/**
 * see DC §3.2 user_submissions.verification
 */
verification: {
fetched_ok?: boolean
http_status?: (number | null)
canonical_url?: (string | null)
origin_source_id?: (string | null)
origin_url?: (string | null)
origin_published_at?: (Timestamp | null)
independent_origin_key?: (string | null)
content_hash?: (string | null)
duplicate_of_item_id?: (string | null)
checks?: {
check: ("link_reachable" | "domain_reputation" | "origin_traced" | "content_matches_origin" | "timestamp_consistent" | "duplicate_check" | "mnpi_screen")
result: ("pass" | "fail" | "n_a")
note?: (string | null)
}[]
}
item_id?: (string | null)
missed_by_system?: (boolean | null)
supplement_run_id?: (string | null)
visibility: ("submitter_and_reviewers" | "shared")
}

export const SCHEMA_VERSION = "contract-0.7.4" as const;
