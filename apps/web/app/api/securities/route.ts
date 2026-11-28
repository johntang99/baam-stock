import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// GET /api/securities?tier=pilot — monitoring list with the latest snapshot (DC §6)
export async function GET(req: Request) {
  const tier = new URL(req.url).searchParams.get("tier");
  return handle(async (db) => json((await db.listSecurities()).filter((s) => !tier || s.coverage_tier === tier)));
}
