import assert from "node:assert/strict";
import { test } from "node:test";

import { checkRunRequest } from "./validate.ts";

const viewer = { userId: "u1", role: "viewer" as const };
const researcher = { userId: "r1", role: "researcher" as const };
const base = { security_ids: ["sec_nvda"], target_ids: ["regular_60m", "regular_60m_move"] };

test("defaults to live + reuse_if_unchanged and dedupes ids", () => {
  const c = checkRunRequest({ ...base, security_ids: ["sec_nvda", "sec_nvda"] }, viewer);
  assert.ok(c.ok);
  if (c.ok) {
    assert.equal(c.req.mode, "live");
    assert.equal(c.req.reuse_policy, "reuse_if_unchanged");
    assert.deepEqual(c.req.security_ids, ["sec_nvda"]);
    assert.equal(c.req.as_of, null);
  }
});

test("viewers may only run live + reuse (DC §6)", () => {
  const r = checkRunRequest({ ...base, mode: "replay", as_of: "2026-12-01T15:00:00Z" }, viewer);
  assert.deepEqual(r.ok ? null : r.status, 403);
  const f = checkRunRequest({ ...base, reuse_policy: "force_recompute" }, viewer);
  assert.deepEqual(f.ok ? null : f.status, 403);
  assert.ok(checkRunRequest({ ...base, mode: "replay", as_of: "2026-12-01T10:00:00-05:00" }, researcher).ok);
});

test("rejects bad input", () => {
  for (const b of [
    null,
    { ...base, security_ids: [] },
    { ...base, security_ids: ["NVDA"] },
    { ...base, target_ids: ["regular_15m"] },
    { ...base, mode: "supplement" },
    { ...base, mode: "replay" }, // no as_of
    { ...base, mode: "replay", as_of: "2026-12-01 10:00" }, // no time zone
  ]) {
    const c = checkRunRequest(b, researcher);
    assert.equal(c.ok, false, JSON.stringify(b));
  }
});

test("as_of is normalised to UTC", () => {
  const c = checkRunRequest({ ...base, mode: "dry_run", as_of: "2026-12-01T10:00:00-05:00" }, researcher);
  assert.ok(c.ok && c.req.as_of === "2026-12-01T15:00:00.000Z");
});
