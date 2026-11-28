import assert from "node:assert/strict";
import { test } from "node:test";

import { etDateTime, etTime, pct, pp } from "./format.ts";

test("times are shown in New York time", () => {
  assert.equal(etTime("2026-12-01T15:20:00.000Z"), "10:20 ET"); // EST (UTC-5)
  assert.equal(etTime("2026-07-01T14:30:00.000Z"), "10:30 ET"); // EDT (UTC-4)
  assert.equal(etDateTime("2026-12-01T21:00:00Z"), "12/01 16:00 ET");
  assert.equal(etTime(null), "—");
});

test("signed percentages", () => {
  assert.equal(pct(0.61), "+0.61%");
  assert.equal(pct(-1.2), "-1.20%");
  assert.equal(pp(0), "0.00pp");
  assert.equal(pct(null), "—");
});
