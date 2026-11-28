import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// GET /api/pipeline-runs/{id} — run and step progress (the page polls this and listens on Realtime)
export async function GET(_req: Request, { params }: { params: Promise<{ pipeline_run_id: string }> }) {
  const { pipeline_run_id } = await params;
  return handle(async (db) => {
    const d = await db.run(pipeline_run_id);
    return d ? json(d) : json({ error: { code: "not_found", message: pipeline_run_id } }, 404);
  });
}
