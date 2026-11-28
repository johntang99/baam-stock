import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// GET /api/events/{id}?version=n — the latest published version, or an older one
export async function GET(req: Request, { params }: { params: Promise<{ event_id: string }> }) {
  const { event_id } = await params;
  const v = new URL(req.url).searchParams.get("version");
  const version = v === null ? undefined : Number(v);
  if (version !== undefined && (!Number.isInteger(version) || version < 1))
    return json({ error: { code: "invalid", message: "version must be a positive integer" } }, 400);
  return handle(async (db) => {
    const d = await db.event(event_id, version);
    return d ? json(d) : json({ error: { code: "not_found", message: event_id } }, 404);
  });
}
