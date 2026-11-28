// View models and the data-source interface of the market pages (DP 2.07; DC §6). Field names come from the
// generated contract types; nothing here redefines a contract field.
import type {
  EventAnalysisVersions,
  EventMilestones,
  Events,
  EventSecurityLinks,
  PipelineRuns,
  PipelineRunSteps,
  PredictionRuns,
  PredictionSettlements,
  Predictions,
  SecurityStateSnapshots,
} from "contracts";

export type Role = "viewer" | "researcher" | "reviewer" | "admin";
export const ROLE_RANK: Record<Role, number> = { viewer: 1, researcher: 2, reviewer: 3, admin: 4 };

export interface Viewer {
  userId: string;
  role: Role;
  email?: string | null;
}

export interface SecuritySummary {
  security_id: string;
  ticker: string;
  legal_name: string;
  coverage_tier: string;
  snapshot: SecurityStateSnapshots | null;
}

export interface PredictionDetail {
  prediction: Predictions;
  run: PredictionRuns | null;
  settlements: PredictionSettlements[];
}

export interface EventRow {
  event: Events;
  security_ids: string[];
  latest: EventAnalysisVersions | null;
}

export interface EventDetail {
  event: Events;
  links: EventSecurityLinks[];
  milestones: EventMilestones[];
  versions: EventAnalysisVersions[]; // every published version, oldest first
  selected: EventAnalysisVersions[]; // one per security: the requested version, else the latest
}

export interface RunDetail {
  run: PipelineRuns;
  steps: PipelineRunSteps[];
}

export type RunMode = "live" | "replay" | "dry_run";
export type ReusePolicy = "reuse_if_unchanged" | "force_recompute";

export interface RunRequest {
  security_ids: string[];
  target_ids: string[];
  mode: RunMode;
  as_of?: string | null;
  reuse_policy: ReusePolicy;
}

export interface PredictionFilter {
  security_id?: string;
  target_id?: string;
  status?: string;
  limit?: number;
}

export interface EventFilter {
  security_id?: string;
  progress_status?: string;
}

export type DataErrorKind = "timeout" | "failure" | "forbidden" | "invalid" | "not_found" | "unauthenticated";

export class DataError extends Error {
  kind: DataErrorKind; // a plain field: Node's type stripping (unit tests) has no parameter properties
  constructor(kind: DataErrorKind, message: string) {
    super(message);
    this.kind = kind;
    this.name = "DataError";
  }
}

export interface DataSource {
  kind: "fixture" | "supabase";
  synthetic: boolean;
  listSecurities(): Promise<SecuritySummary[]>;
  security(ticker: string): Promise<SecuritySummary | null>;
  predictions(f: PredictionFilter): Promise<Predictions[]>;
  prediction(id: string): Promise<PredictionDetail | null>;
  events(f: EventFilter): Promise<EventRow[]>;
  event(id: string, version?: number): Promise<EventDetail | null>;
  requestRun(viewer: Viewer, req: RunRequest): Promise<{ pipeline_run_id: string; created: boolean }>;
  cancelRun(viewer: Viewer, id: string): Promise<string>;
  run(id: string): Promise<RunDetail | null>;
  runs(limit: number): Promise<PipelineRuns[]>;
  refresh(securityId: string): Promise<{ job_id: string | null; reused_snapshot_id: string | null }>;
}

// Targets the one-click run offers (DC target_id values; the to-close / next-session ones abstain until their
// models exist, OQ-57).
export const RUN_TARGETS = ["regular_60m", "regular_60m_move", "regular_to_close", "next_regular_session"] as const;

export const STEP_LABELS: Record<string, string> = {
  collect_evidence: "采集证据",
  verify_dedupe: "核验去重",
  analyze_events: "事件分析",
  build_snapshot: "证券快照",
  readiness_check: "就绪检查",
  infer: "推断",
  publish: "发布",
  schedule_settlement: "安排结算",
};
