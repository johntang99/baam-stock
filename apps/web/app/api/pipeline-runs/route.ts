import { handle, json } from "@/lib/api";
import { checkRunRequest } from "@/lib/data/validate";

export const dynamic = "force-dynamic";

// POST /api/pipeline-runs — one-click run (DC §6): 202 {pipeline_run_id}; the same request again returns that run
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json({ error: { code: "invalid", message: "body must be JSON" } }, 400);
  }
  return handle(async (db, viewer) => {
    const c = checkRunRequest(body, viewer);
    if (!c.ok) return json({ error: { code: c.status === 403 ? "forbidden" : "invalid", message: c.error } }, c.status);
    const r = await db.requestRun(viewer, c.req);
    return json(r, r.created ? 202 : 200);
  });
}

// GET /api/pipeline-runs?limit= — run history (own runs for viewers, all for researchers: RLS)
export async function GET(req: Request) {
  const limit = Math.min(Number(new URL(req.url).searchParams.get("limit") ?? 20) || 20, 100);
  return handle(async (db) => json(await db.runs(limit)));
}
