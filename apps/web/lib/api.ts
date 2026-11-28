// Shared Route Handler helpers (DC §6, §9 error mapping).
import { NextResponse } from "next/server";

import { getData, getViewer } from "./data/index.ts";
import { DataError } from "./data/types.ts";
import type { DataSource, Viewer } from "./data/types.ts";

const STATUS: Record<string, number> = {
  unauthenticated: 401,
  forbidden: 403,
  invalid: 400,
  not_found: 404,
  timeout: 504,
  failure: 502,
};

export function json(data: unknown, status = 200): NextResponse {
  return NextResponse.json(data, { status, headers: { "cache-control": "no-store" } });
}

export function errorResponse(e: unknown): NextResponse {
  if (e instanceof DataError) return json({ error: { code: e.kind, message: e.message } }, STATUS[e.kind] ?? 500);
  return json({ error: { code: "internal", message: "unexpected error" } }, 500);
}

/** Runs a handler with the viewer and data source; no session or no role -> 401. */
export async function handle(fn: (db: DataSource, viewer: Viewer) => Promise<NextResponse>): Promise<NextResponse> {
  try {
    const viewer = await getViewer();
    if (!viewer) return json({ error: { code: "unauthenticated", message: "sign in first" } }, 401);
    return await fn(await getData(), viewer);
  } catch (e) {
    return errorResponse(e);
  }
}
