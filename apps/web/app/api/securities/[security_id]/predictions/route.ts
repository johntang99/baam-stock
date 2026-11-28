import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// GET /api/securities/{id}/predictions?target_id=&status=&limit=
export async function GET(req: Request, { params }: { params: Promise<{ security_id: string }> }) {
  const { security_id } = await params;
  const q = new URL(req.url).searchParams;
  const limit = Math.min(Number(q.get("limit") ?? 50) || 50, 200);
  return handle(async (db) =>
    json(
      await db.predictions({
        security_id,
        target_id: q.get("target_id") ?? undefined,
        status: q.get("status") ?? undefined,
        limit,
      }),
    ),
  );
}
