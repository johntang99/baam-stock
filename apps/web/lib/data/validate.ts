// Request-body checks for POST /api/pipeline-runs (DC §6). The database function repeats the role rules; this
// gives the page a clear 400 / 403 before the round trip.
import { RUN_TARGETS, ROLE_RANK } from "./types.ts";
import type { RunRequest, Viewer } from "./types.ts";

export type Checked = { ok: true; req: RunRequest } | { ok: false; status: 400 | 403; error: string };

const SEC = /^sec_[a-z0-9]{1,16}$/;

export function checkRunRequest(body: unknown, viewer: Viewer): Checked {
  if (typeof body !== "object" || body === null) return { ok: false, status: 400, error: "body must be a JSON object" };
  const b = body as Record<string, unknown>;
  const secs = b.security_ids;
  const tgts = b.target_ids;
  if (!Array.isArray(secs) || secs.length === 0 || secs.length > 6 || !secs.every((s) => typeof s === "string" && SEC.test(s)))
    return { ok: false, status: 400, error: "security_ids: 1-6 ids like sec_nvda" };
  if (!Array.isArray(tgts) || tgts.length === 0 || !tgts.every((t) => (RUN_TARGETS as readonly string[]).includes(t as string)))
    return { ok: false, status: 400, error: `target_ids: any of ${RUN_TARGETS.join(", ")}` };
  const mode = b.mode ?? "live";
  if (mode !== "live" && mode !== "replay" && mode !== "dry_run") return { ok: false, status: 400, error: "mode: live | replay | dry_run" };
  const reuse = b.reuse_policy ?? "reuse_if_unchanged";
  if (reuse !== "reuse_if_unchanged" && reuse !== "force_recompute")
    return { ok: false, status: 400, error: "reuse_policy: reuse_if_unchanged | force_recompute" };
  let asOf: string | null = null;
  if (mode !== "live") {
    if (typeof b.as_of !== "string" || Number.isNaN(Date.parse(b.as_of)) || !/(Z|[+-]\d\d:\d\d)$/.test(b.as_of))
      return { ok: false, status: 400, error: "as_of: ISO timestamp with time zone (replay / dry_run)" };
    asOf = new Date(b.as_of).toISOString();
  }
  if (ROLE_RANK[viewer.role] < ROLE_RANK.researcher && (mode !== "live" || reuse !== "reuse_if_unchanged"))
    return { ok: false, status: 403, error: "viewer may only run live + reuse_if_unchanged" };
  return {
    ok: true,
    req: { security_ids: [...new Set(secs as string[])], target_ids: [...new Set(tgts as string[])], mode, as_of: asOf, reuse_policy: reuse },
  };
}
