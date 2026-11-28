import assert from "node:assert/strict";
import { test } from "node:test";

import { fixtureSource, resetFixture } from "./fixture.ts";
import { DataError } from "./types.ts";
import { wrap } from "./wrap.ts";

process.env.FIXTURE_STEP_MS = "100";
const viewer = { userId: "u1", role: "viewer" as const };
const req = { security_ids: ["sec_nvda"], target_ids: ["regular_60m"], mode: "live" as const, reuse_policy: "reuse_if_unchanged" as const };

test("four synthetic pilot securities with snapshots", async () => {
  resetFixture();
  const s = await fixtureSource().listSecurities();
  assert.deepEqual(s.map((x) => x.ticker), ["NVDA", "AMD", "AVGO", "MU"]);
  assert.ok(s.every((x) => x.snapshot && x.snapshot.security_id === x.security_id));
  assert.equal(s.find((x) => x.ticker === "MU")?.snapshot?.data_quality, "stale");
});

test("a run moves queued -> running -> succeeded through all 8 steps", async () => {
  resetFixture();
  let t = 0;
  const db = fixtureSource(() => t);
  const { pipeline_run_id: id, created } = await db.requestRun(viewer, req);
  assert.ok(created);
  assert.equal((await db.run(id))?.run.status, "queued");
  t = 250;
  assert.equal((await db.run(id))?.run.status, "running");
  t = 100 * 10;
  const d = await db.run(id);
  assert.equal(d?.run.status, "succeeded");
  assert.equal(d?.steps.length, 8);
  assert.ok(d?.steps.every((s) => s.status === "succeeded" || s.status === "skipped"));
});

test("three clicks within a minute give one run; a viewer cannot cancel another user's run", async () => {
  resetFixture();
  let t = 0;
  const db = fixtureSource(() => t);
  const a = await db.requestRun(viewer, req);
  t = 20_000;
  const b = await db.requestRun(viewer, req);
  t = 59_000;
  const c = await db.requestRun(viewer, req);
  assert.equal(a.pipeline_run_id, b.pipeline_run_id);
  assert.equal(b.pipeline_run_id, c.pipeline_run_id);
  assert.ok(!b.created && !c.created);
  t = 61_000;
  assert.ok((await db.requestRun(viewer, req)).created);
  await assert.rejects(db.cancelRun({ userId: "u2", role: "viewer" }, a.pipeline_run_id), (e: unknown) => e instanceof DataError);
});

test("cancel stops the remaining steps", async () => {
  resetFixture();
  let t = 0;
  const db = fixtureSource(() => t);
  const { pipeline_run_id: id } = await db.requestRun({ userId: "r1", role: "researcher" }, req);
  t = 450; // three steps done, the fourth running
  assert.equal(await db.cancelRun({ userId: "r1", role: "researcher" }, id), "cancelled");
  t = 5000;
  const d = await db.run(id);
  assert.equal(d?.run.status, "cancelled");
  assert.deepEqual(d?.steps.slice(3).map((s) => s.status), Array(5).fill("skipped"));
});

test("wrapped states: empty, error, timeout", async () => {
  resetFixture();
  assert.deepEqual(await wrap(fixtureSource(), 1000, "empty").listSecurities(), []);
  await assert.rejects(wrap(fixtureSource(), 1000, "error").listSecurities(), (e: unknown) => e instanceof DataError && e.kind === "failure");
  await assert.rejects(wrap(fixtureSource(), 50, "timeout").listSecurities(), (e: unknown) => e instanceof DataError && e.kind === "timeout");
});
