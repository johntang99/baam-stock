// Read-only replay reports (DP 1.19). The Python replay (`sr replay`) writes one JSON file per prediction to
// data/replay/reports/<prediction_id>.json; this module only reads them — no database credentials in the web app.
import { promises as fs } from "node:fs";
import path from "node:path";

import type {
  ModelVersions,
  PredictionRuns,
  PredictionSettlements,
  Predictions,
  ReferenceQuotes,
  SecurityStateSnapshots,
} from "@/lib/contracts";

export interface ReportCheck {
  check: string;
  result: "pass" | "FAIL" | "n/a";
  note: string;
}

export interface ReplayReport {
  synthetic: boolean;
  prediction: Predictions;
  run: Partial<PredictionRuns>;
  snapshot: Partial<SecurityStateSnapshots>;
  model: Partial<ModelVersions>;
  features: Record<string, unknown>;
  t0_quote: Partial<ReferenceQuotes> | null;
  end_quote: Partial<ReferenceQuotes> | null;
  settlement: Partial<PredictionSettlements> | null;
  settlement_versions: number;
  checks: ReportCheck[];
}

// Prediction ids are ULID-based ("pred_" + base32); anything else is rejected before touching the file system.
const ID = /^pred_[0-9A-Za-z]{1,64}$/;

export function isPredictionId(id: string): boolean {
  return ID.test(id);
}

export function reportDir(): string {
  return process.env.REPLAY_REPORT_DIR ?? path.join(process.cwd(), "..", "..", "data", "replay", "reports");
}

export async function loadReport(id: string, dir: string = reportDir()): Promise<ReplayReport | null> {
  if (!isPredictionId(id)) return null;
  const file = path.join(dir, `${id}.json`);
  if (path.dirname(file) !== path.resolve(dir)) return null; // never leave the report directory
  try {
    return JSON.parse(await fs.readFile(file, "utf8")) as ReplayReport;
  } catch {
    return null;
  }
}

export async function listReports(dir: string = reportDir()): Promise<ReplayReport[]> {
  let names: string[] = [];
  try {
    names = await fs.readdir(dir);
  } catch {
    return [];
  }
  const ids = names.filter((n) => n.endsWith(".json")).map((n) => n.slice(0, -5)).filter(isPredictionId);
  const out = (await Promise.all(ids.map((id) => loadReport(id, dir)))).filter((r): r is ReplayReport => r !== null);
  return out.sort((a, b) => String(a.prediction.published_at).localeCompare(String(b.prediction.published_at)));
}

export function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toPrecision(6);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
