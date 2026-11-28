import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// POST /api/pipeline-runs/{id}/cancel — stops before the next step; published parts are kept
export async function POST(_req: Request, { params }: { params: Promise<{ pipeline_run_id: string }> }) {
  const { pipeline_run_id } = await params;
  return handle(async (db, viewer) => json({ status: await db.cancelRun(viewer, pipeline_run_id) }));
}
