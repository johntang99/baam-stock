import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// POST /api/securities/{id}/refresh — 202 {job_id} when a snapshot job is queued, 200 when a valid one is reused
export async function POST(_req: Request, { params }: { params: Promise<{ security_id: string }> }) {
  const { security_id } = await params;
  return handle(async (db) => {
    const r = await db.refresh(security_id);
    return r.reused_snapshot_id ? json(r, 200) : json(r, 202);
  });
}
