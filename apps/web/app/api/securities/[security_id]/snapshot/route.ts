import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// GET /api/securities/{id}/snapshot — the latest snapshot (DC §6)
export async function GET(_req: Request, { params }: { params: Promise<{ security_id: string }> }) {
  const { security_id } = await params;
  return handle(async (db) => {
    const s = (await db.listSecurities()).find((x) => x.security_id === security_id);
    return s?.snapshot ? json(s.snapshot) : json({ error: { code: "not_found", message: security_id } }, 404);
  });
}
