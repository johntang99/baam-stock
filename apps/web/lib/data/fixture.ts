// Fixture data source (DP 2.07: "前端可先用 contracts examples"). SYNTHETIC / 虚构 only: built from
// packages/contracts/examples, varied per pilot security. Used for local development and the e2e tests; pipeline
// runs are simulated in memory (steps advance on a timer) so the one-click run page can be exercised end to end.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import type {
  EventAnalysisVersions,
  Events,
  EventSecurityLinks,
  PipelineRuns,
  PipelineRunSteps,
  PredictionSettlements,
  Predictions,
  SecurityStateSnapshots,
} from "contracts";

import { DataError, ROLE_RANK, STEP_LABELS } from "./types.ts";
import type {
  DataSource,
  EventDetail,
  EventFilter,
  EventRow,
  PredictionDetail,
  PredictionFilter,
  RunDetail,
  RunRequest,
  SecuritySummary,
  Viewer,
} from "./types.ts";

function examplesDir(): string {
  let d = process.cwd();
  for (let i = 0; i < 6; i++) {
    const p = path.join(d, "packages", "contracts", "examples");
    if (existsSync(p)) return p;
    d = path.dirname(d);
  }
  throw new Error("packages/contracts/examples not found");
}

function ex<T>(name: string): T {
  return JSON.parse(readFileSync(path.join(examplesDir(), `${name}.json`), "utf8")) as T;
}

const PILOT: { ticker: string; legal_name: string; day: number; rel: number; quality: string }[] = [
  { ticker: "NVDA", legal_name: "NVIDIA Corporation", day: 0.61, rel: 0.22, quality: "ok" },
  { ticker: "AMD", legal_name: "Advanced Micro Devices, Inc.", day: -0.84, rel: -1.12, quality: "ok" },
  { ticker: "AVGO", legal_name: "Broadcom Inc.", day: 0.35, rel: -0.04, quality: "partial" },
  { ticker: "MU", legal_name: "Micron Technology, Inc.", day: 1.48, rel: 1.09, quality: "stale" },
];

interface Store {
  securities: SecuritySummary[];
  predictions: Predictions[];
  settlements: PredictionSettlements[];
  events: Events[];
  links: EventSecurityLinks[];
  analyses: EventAnalysisVersions[];
  runs: Map<string, { run: PipelineRuns; createdMs: number; cancelledAtStep: number | null }>;
}

function build(): Store {
  const snap0 = ex<SecurityStateSnapshots>("security_state_snapshots.ex81_nvda_plain_day");
  const p60 = ex<Predictions>("predictions.ex81_nvda_regular_60m");
  const pmove = ex<Predictions>("predictions.ex81_nvda_regular_60m_move");
  const pevent = ex<Predictions>("predictions.ex82_nvda_regular_60m_event");
  const stl = ex<PredictionSettlements>("prediction_settlements.ex81_nvda_regular_60m");
  const securities: SecuritySummary[] = PILOT.map((p) => {
    const k = p.ticker.toLowerCase();
    const stale = p.quality === "stale";
    const snapshot: SecurityStateSnapshots = {
      ...snap0,
      snapshot_id: `snap_${k}_20261201_1520`,
      security_id: `sec_${k}`,
      benchmark_version_id: `bmv_semis_peer_ex_${k}_v1`,
      day_return_pct: p.day,
      day_relative_pp: p.quality === "partial" ? null : p.rel,
      data_quality: p.quality as SecurityStateSnapshots["data_quality"],
      run_state: (p.quality === "ok" ? "complete" : "degraded") as SecurityStateSnapshots["run_state"],
      quality_issues: stale
        ? [{ issue: "stale_quotes", lag_s: 95 }]
        : p.quality === "partial"
          ? [{ issue: "benchmark_unavailable" }]
          : [],
      last_valid_at: stale ? "2026-12-01T15:10:00.600Z" : snap0.last_valid_at,
      // same wording as config/snapshot.yaml summary templates
      explanation_summary:
        p.quality === "partial"
          ? "监测来源范围内暂未发现新催化剂；基准不可计算，仅显示绝对涨跌。"
          : `监测来源范围内暂未发现新催化剂；相对 ${p.rel > 0 ? "+" : ""}${p.rel.toFixed(2)}pp 未找到专属原因。`,
      dedupe_key: `sec_${k}|2026-12-01T15:18:44Z|2026-12-01T15:19:59Z`,
    };
    return { security_id: `sec_${k}`, ticker: p.ticker, legal_name: p.legal_name, coverage_tier: "pilot", snapshot };
  });
  const predictions: Predictions[] = [];
  for (const p of PILOT) {
    const k = p.ticker.toLowerCase();
    for (const base of [p60, pmove]) {
      predictions.push({
        ...base,
        prediction_id: base.prediction_id.replace("nvda", k),
        run_id: base.run_id.replace("nvda", k),
        security_id: `sec_${k}`,
      });
    }
  }
  predictions.push(pevent);
  return {
    securities,
    predictions,
    settlements: [stl],
    events: [ex<Events>("events.ex82_policy_export")],
    links: ["nvda", "amd", "mu"].map((k) => ex<EventSecurityLinks>(`event_security_links.ex82_${k}`)),
    analyses: [ex<EventAnalysisVersions>("event_analysis_versions.ex82_nvda_flash")],
    runs: new Map(),
  };
}

const g = globalThis as unknown as { __baamFixture?: Store };
function store(): Store {
  if (!g.__baamFixture) g.__baamFixture = build();
  return g.__baamFixture;
}

export function resetFixture(): void {
  g.__baamFixture = build();
}

const STEPS = Object.keys(STEP_LABELS);
const stepMs = (): number => Number(process.env.FIXTURE_STEP_MS ?? 600);

function progress(entry: { run: PipelineRuns; createdMs: number; cancelledAtStep: number | null }, now: number): RunDetail {
  const per = stepMs();
  const elapsed = Math.max(0, now - entry.createdMs);
  const doneByTime = Math.floor(elapsed / per) - 1; // the first interval is the queue wait
  const n = STEPS.length;
  const run = { ...entry.run };
  const stop = entry.cancelledAtStep;
  const steps: PipelineRunSteps[] = [];
  entry.run.security_ids.forEach((sec, si) => {
    STEPS.forEach((step, i) => {
      const k = si * n + i;
      let status: PipelineRunSteps["status"] = "pending";
      if (stop !== null && k >= stop) status = "skipped";
      else if (k < doneByTime) status = i < 3 ? "skipped" : "succeeded"; // no evidence sources in the fixture
      else if (k === doneByTime) status = "running";
      steps.push({
        pipeline_run_id: run.pipeline_run_id,
        step_no: k + 1,
        step: step as PipelineRunSteps["step"],
        security_id: sec,
        status,
        attempt: status === "pending" ? 0 : 1,
        detail: status === "skipped" && stop !== null && k >= stop ? { reason: "cancelled" } : {},
      } as PipelineRunSteps);
    });
  });
  if (stop !== null) run.status = "cancelled";
  else if (doneByTime < 0) run.status = "queued";
  else if (doneByTime < steps.length) run.status = "running";
  else {
    run.status = "succeeded";
    run.outputs = { reused: false, synthetic: true, prediction_ids: [], abstained: [] };
  }
  return { run, steps };
}

export function fixtureSource(now: () => number = Date.now): DataSource {
  const s = store();
  return {
    kind: "fixture",
    synthetic: true,
    async listSecurities() {
      return s.securities;
    },
    async security(ticker: string) {
      return s.securities.find((x) => x.ticker.toLowerCase() === ticker.toLowerCase()) ?? null;
    },
    async predictions(f: PredictionFilter) {
      return s.predictions
        .filter((p) => !f.security_id || p.security_id === f.security_id)
        .filter((p) => !f.target_id || p.target_row_id === `tgt_${f.target_id}_v1`)
        .filter((p) => !f.status || p.status === f.status)
        .slice(0, f.limit ?? 100);
    },
    async prediction(id: string): Promise<PredictionDetail | null> {
      const p = s.predictions.find((x) => x.prediction_id === id);
      if (!p) return null;
      return { prediction: p, run: null, settlements: s.settlements.filter((x) => x.prediction_id === id) };
    },
    async events(f: EventFilter): Promise<EventRow[]> {
      return s.events
        .filter((e) => !f.progress_status || e.progress_status === f.progress_status)
        .map((e) => ({
          event: e,
          security_ids: s.links.filter((l) => l.event_id === e.event_id).map((l) => l.security_id),
          latest: s.analyses.filter((a) => a.event_id === e.event_id).at(-1) ?? null,
        }))
        .filter((r) => !f.security_id || r.security_ids.includes(f.security_id));
    },
    async event(id: string, version?: number): Promise<EventDetail | null> {
      const e = s.events.find((x) => x.event_id === id);
      if (!e) return null;
      const versions = s.analyses.filter((a) => a.event_id === id);
      const bySec = new Map<string, EventAnalysisVersions>();
      for (const a of versions) if (version === undefined || a.analysis_version === version) bySec.set(a.security_id, a);
      return { event: e, links: s.links.filter((l) => l.event_id === id), milestones: [], versions, selected: [...bySec.values()] };
    },
    async requestRun(viewer: Viewer, req: RunRequest) {
      if (ROLE_RANK[viewer.role] < ROLE_RANK.researcher && (req.mode !== "live" || req.reuse_policy !== "reuse_if_unchanged"))
        throw new DataError("forbidden", "viewer may only run live + reuse_if_unchanged");
      const t = now();
      const key = [[...req.security_ids].sort().join(","), [...req.target_ids].sort().join(","), req.mode, req.reuse_policy, viewer.userId].join("|");
      for (const e of s.runs.values()) {
        const k2 = [[...e.run.security_ids].sort().join(","), [...e.run.target_ids].sort().join(","), e.run.mode, e.run.reuse_policy, e.run.requested_by].join("|");
        const st = progress(e, t).run.status;
        if (k2 === key && t - e.createdMs < 60_000 && st !== "failed" && st !== "cancelled")
          return { pipeline_run_id: e.run.pipeline_run_id, created: false }; // AC-35
      }
      const id = `pr_FIXTURE${String(s.runs.size + 1).padStart(4, "0")}`;
      const run: PipelineRuns = {
        pipeline_run_id: id,
        security_ids: req.security_ids,
        target_ids: req.target_ids as PipelineRuns["target_ids"],
        trigger_type: "on_demand",
        requested_by: viewer.userId,
        mode: req.mode,
        submission_ids: [],
        as_of: req.mode === "live" || !req.as_of ? new Date(t).toISOString() : req.as_of,
        status: "queued",
        reuse_policy: req.reuse_policy,
        outputs: {},
        sla_ms: 90000,
        idempotency_key: `${key}|${t}`,
      };
      s.runs.set(id, { run, createdMs: t, cancelledAtStep: null });
      return { pipeline_run_id: id, created: true };
    },
    async cancelRun(viewer: Viewer, id: string) {
      const e = s.runs.get(id);
      if (!e) throw new DataError("not_found", id);
      if (ROLE_RANK[viewer.role] < ROLE_RANK.researcher && e.run.requested_by !== viewer.userId)
        throw new DataError("forbidden", "not your run");
      const cur = progress(e, now());
      if (cur.run.status === "queued" || cur.run.status === "running") {
        e.cancelledAtStep = Math.max(0, cur.steps.findIndex((x) => x.status === "running" || x.status === "pending"));
        return "cancelled";
      }
      return cur.run.status;
    },
    async run(id: string) {
      const e = s.runs.get(id);
      return e ? progress(e, now()) : null;
    },
    async runs(limit: number) {
      return [...s.runs.values()]
        .map((e) => progress(e, now()).run)
        .reverse()
        .slice(0, limit);
    },
    async refresh(securityId: string) {
      const x = s.securities.find((v) => v.security_id === securityId);
      if (!x) throw new DataError("invalid", "unknown security");
      return x.snapshot?.data_quality === "ok"
        ? { job_id: null, reused_snapshot_id: x.snapshot.snapshot_id }
        : { job_id: `job_FIXTURE_${securityId}`, reused_snapshot_id: null };
    },
  };
}
