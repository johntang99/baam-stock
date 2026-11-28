// Supabase data source (DP 2.07). Server side only: every query runs with the signed-in user's session, so the row
// policies of migration 0007 decide what is visible (DC §10). Writes are the three request functions only; the
// web app never holds the service-role key.
import type { SupabaseClient } from "@supabase/supabase-js";
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

import { DataError } from "./types.ts";
import type { DataSource, EventFilter, PredictionFilter, RunRequest, SecuritySummary, Viewer } from "./types.ts";

interface PgError {
  code?: string;
  message: string;
}

export function mapError(e: PgError): DataError {
  if (e.code === "42501") return new DataError("forbidden", e.message);
  if (e.code === "22023") return new DataError("invalid", e.message);
  if (e.code === "PGRST301" || e.code === "401") return new DataError("unauthenticated", e.message);
  return new DataError("failure", e.message);
}

function rows<T>(r: { data: unknown; error: PgError | null }): T[] {
  if (r.error) throw mapError(r.error);
  return (r.data ?? []) as T[];
}

function one<T>(r: { data: unknown; error: PgError | null }): T | null {
  return rows<T>(r)[0] ?? null;
}

export function supabaseSource(db: SupabaseClient): DataSource {
  async function targetRows(targetId: string): Promise<string[]> {
    const r = await db.from("prediction_targets").select("target_row_id").eq("target_id", targetId);
    return rows<{ target_row_id: string }>(r).map((x) => x.target_row_id);
  }

  async function summaries(filterTicker?: string): Promise<SecuritySummary[]> {
    const secs = rows<{ security_id: string; company_id: string; coverage_tier: string }>(
      await db.from("securities").select("security_id, company_id, coverage_tier").in("coverage_tier", ["pilot", "batch2"]),
    );
    const ids = rows<{ security_id: string; value: string }>(
      await db.from("security_identifiers").select("security_id, value").eq("id_type", "ticker").is("valid_to", null),
    );
    const cos = rows<{ company_id: string; legal_name: string }>(await db.from("companies").select("company_id, legal_name"));
    const out: SecuritySummary[] = [];
    for (const s of secs) {
      const ticker = ids.find((i) => i.security_id === s.security_id)?.value ?? s.security_id;
      if (filterTicker && ticker.toLowerCase() !== filterTicker.toLowerCase()) continue;
      const snap = one<SecurityStateSnapshots>(
        await db
          .from("security_state_snapshots")
          .select("*")
          .eq("security_id", s.security_id)
          .order("analysis_as_of", { ascending: false })
          .limit(1),
      );
      out.push({
        security_id: s.security_id,
        ticker,
        legal_name: cos.find((c) => c.company_id === s.company_id)?.legal_name ?? "",
        coverage_tier: s.coverage_tier,
        snapshot: snap,
      });
    }
    return out.sort((a, b) => a.coverage_tier.localeCompare(b.coverage_tier) * -1 || a.ticker.localeCompare(b.ticker));
  }

  return {
    kind: "supabase",
    synthetic: false,
    listSecurities: () => summaries(),
    async security(ticker: string) {
      return (await summaries(ticker))[0] ?? null;
    },
    async predictions(f: PredictionFilter) {
      let q = db.from("predictions").select("*").order("published_at", { ascending: false }).limit(f.limit ?? 100);
      if (f.security_id) q = q.eq("security_id", f.security_id);
      if (f.status) q = q.eq("status", f.status);
      if (f.target_id) q = q.in("target_row_id", await targetRows(f.target_id));
      return rows<Predictions>(await q);
    },
    async prediction(id: string) {
      const p = one<Predictions>(await db.from("predictions").select("*").eq("prediction_id", id));
      if (!p) return null;
      const run = one<PredictionRuns>(await db.from("prediction_runs").select("*").eq("run_id", p.run_id));
      const settlements = rows<PredictionSettlements>(
        await db.from("prediction_settlements").select("*").eq("prediction_id", id).order("settlement_version"),
      );
      return { prediction: p, run, settlements };
    },
    async events(f: EventFilter) {
      let q = db.from("events").select("*").order("first_seen_at", { ascending: false }).limit(100);
      if (f.progress_status) q = q.eq("progress_status", f.progress_status);
      const evs = rows<Events>(await q);
      if (evs.length === 0) return [];
      const ids = evs.map((e) => e.event_id);
      const links = rows<EventSecurityLinks>(await db.from("event_security_links").select("*").in("event_id", ids));
      const an = rows<EventAnalysisVersions>(
        await db.from("event_analysis_versions").select("*").in("event_id", ids).order("analysis_version"),
      );
      return evs
        .map((e) => ({
          event: e,
          security_ids: links.filter((l) => l.event_id === e.event_id).map((l) => l.security_id),
          latest: an.filter((a) => a.event_id === e.event_id).at(-1) ?? null,
        }))
        .filter((r) => !f.security_id || r.security_ids.includes(f.security_id));
    },
    async event(id: string, version?: number) {
      const e = one<Events>(await db.from("events").select("*").eq("event_id", id));
      if (!e) return null;
      const links = rows<EventSecurityLinks>(await db.from("event_security_links").select("*").eq("event_id", id));
      const milestones = rows<EventMilestones>(await db.from("event_milestones").select("*").eq("event_id", id));
      const versions = rows<EventAnalysisVersions>(
        await db.from("event_analysis_versions").select("*").eq("event_id", id).order("analysis_version"),
      );
      const bySec = new Map<string, EventAnalysisVersions>();
      for (const a of versions) if (version === undefined || a.analysis_version === version) bySec.set(a.security_id, a);
      return { event: e, links, milestones, versions, selected: [...bySec.values()] };
    },
    async requestRun(_viewer: Viewer, req: RunRequest) {
      const r = await db.rpc("request_pipeline_run", {
        p_security_ids: req.security_ids,
        p_target_ids: req.target_ids,
        p_mode: req.mode,
        p_as_of: req.as_of ?? null,
        p_reuse_policy: req.reuse_policy,
      });
      const x = one<{ pipeline_run_id: string; created: boolean }>(r);
      if (!x) throw new DataError("failure", "no run returned");
      return x;
    },
    async cancelRun(_viewer: Viewer, id: string) {
      const r = await db.rpc("cancel_pipeline_run", { p_pipeline_run_id: id });
      if (r.error) throw mapError(r.error);
      return String(r.data);
    },
    async run(id: string) {
      const run = one<PipelineRuns>(await db.from("pipeline_runs").select("*").eq("pipeline_run_id", id));
      if (!run) return null;
      const steps = rows<PipelineRunSteps>(
        await db.from("pipeline_run_steps").select("*").eq("pipeline_run_id", id).order("step_no"),
      );
      return { run, steps };
    },
    async runs(limit: number) {
      return rows<PipelineRuns>(await db.from("pipeline_runs").select("*").order("as_of", { ascending: false }).limit(limit));
    },
    async refresh(securityId: string) {
      const x = one<{ job_id: string | null; reused_snapshot_id: string | null }>(
        await db.rpc("request_refresh", { p_security_id: securityId }),
      );
      return x ?? { job_id: null, reused_snapshot_id: null };
    },
  };
}
