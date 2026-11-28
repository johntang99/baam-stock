// node --test --experimental-strip-types (Node >= 22). SYNTHETIC reports only.
import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import { fmt, isPredictionId, listReports, loadReport } from "./replay.ts";

function report(id: string, publishedAt: string) {
  return {
    synthetic: true,
    prediction: { prediction_id: id, published_at: publishedAt, target_row_id: "tgt_regular_60m_v1", status: "settled" },
    run: {},
    snapshot: {},
    model: {},
    features: {},
    t0_quote: null,
    end_quote: null,
    settlement: null,
    settlement_versions: 0,
    checks: [{ check: "x", result: "pass", note: "" }],
  };
}

async function dir(): Promise<string> {
  const d = await fs.mkdtemp(path.join(os.tmpdir(), "replay-"));
  await fs.writeFile(path.join(d, "pred_B.json"), JSON.stringify(report("pred_B", "2026-12-10 15:30:00+00:00")));
  await fs.writeFile(path.join(d, "pred_A.json"), JSON.stringify(report("pred_A", "2026-12-10 15:00:00+00:00")));
  await fs.writeFile(path.join(d, "notes.txt"), "ignored");
  await fs.writeFile(path.join(d, "..secret.json"), "{}"); // not a prediction id: never listed
  return d;
}

test("only well-formed prediction ids are accepted", () => {
  assert.equal(isPredictionId("pred_01M8GQDG43RT31HDYK44ATCMRM"), true);
  for (const bad of ["../etc/passwd", "pred_../../x", "pred_a/b", "pred_", "run_123", "pred_a.json", ""]) {
    assert.equal(isPredictionId(bad), false, bad);
  }
});

test("loadReport reads a report and refuses anything outside the directory", async () => {
  const d = await dir();
  const r = await loadReport("pred_A", d);
  assert.equal(r?.prediction.prediction_id, "pred_A");
  assert.equal(await loadReport("../pred_A", d), null);
  assert.equal(await loadReport("pred_missing", d), null);
});

test("listReports lists prediction reports in publish order", async () => {
  const d = await dir();
  const rs = await listReports(d);
  assert.deepEqual(
    rs.map((r) => r.prediction.prediction_id),
    ["pred_A", "pred_B"],
  );
  assert.deepEqual(await listReports(path.join(d, "nope")), []);
});

test("fmt renders empty values as a dash", () => {
  assert.equal(fmt(null), "—");
  assert.equal(fmt(undefined), "—");
  assert.equal(fmt(0.123456789), "0.123457");
  assert.equal(fmt({ a: 1 }), '{"a":1}');
});
