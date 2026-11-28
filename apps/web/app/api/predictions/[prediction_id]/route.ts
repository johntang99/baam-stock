import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// GET /api/predictions/{id} — prediction, run and every settlement version
export async function GET(_req: Request, { params }: { params: Promise<{ prediction_id: string }> }) {
  const { prediction_id } = await params;
  return handle(async (db) => {
    const d = await db.prediction(prediction_id);
    return d ? json(d) : json({ error: { code: "not_found", message: prediction_id } }, 404);
  });
}
