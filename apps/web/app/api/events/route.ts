import { handle, json } from "@/lib/api";

export const dynamic = "force-dynamic";

// GET /api/events?security_id=&progress_status=
export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  return handle(async (db) =>
    json(await db.events({ security_id: q.get("security_id") ?? undefined, progress_status: q.get("progress_status") ?? undefined })),
  );
}
