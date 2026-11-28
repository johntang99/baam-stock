// One-click run (DP 2.08, 2.15; AC-34 / AC-35 page side). SYNTHETIC fixture: steps advance on a timer.
import { expect, test } from "@playwright/test";

test("stock detail 运行 -> progress -> done; a repeat click returns the same run", async ({ page }) => {
  await page.goto("/stock/AMD");
  await page.getByTestId("run-button").click();
  await page.waitForURL(/\/ops\/run\/pr_/);
  const id = page.url().split("/").pop()!;
  await expect(page.getByTestId("run-progress")).toBeVisible();
  await expect(page.getByTestId("run-status")).toHaveText("已完成", { timeout: 15_000 });
  await expect(page.locator("[data-testid^=step-]")).toHaveCount(8);
  await page.screenshot({ path: "test-results/screens/run-done.png", fullPage: true });
  // AC-35: the same request again within a minute -> the same pipeline_run_id, twice
  for (let i = 0; i < 2; i++) {
    const r = await page.request.post("/api/pipeline-runs", {
      data: { security_ids: ["sec_amd"], target_ids: ["regular_60m", "regular_60m_move"], mode: "live" },
    });
    expect(r.status()).toBe(200);
    expect((await r.json()).pipeline_run_id).toBe(id);
  }
  await page.goto("/ops/run");
  await expect(page.getByTestId("run-history")).toContainText(id);
});

test("run panel: cancel stops the remaining steps", async ({ page }) => {
  await page.goto("/ops/run");
  await page.getByLabel("MU").check();
  await page.getByTestId("run-submit").click();
  await page.waitForURL(/\/ops\/run\/pr_/);
  await expect(page.getByTestId("run-status")).toHaveText(/运行中|排队中/);
  await page.getByTestId("cancel-button").click();
  await expect(page.getByTestId("run-status")).toHaveText("已取消");
  await expect(page.getByTestId("run-outputs")).toContainText("已发布的部分保持不变");
  await expect(page.locator("[data-status=skipped]").first()).toBeVisible();
});

test("viewer: live only (DC §6)", async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: "fixture_role", value: "viewer", url: baseURL! }]);
  await page.goto("/ops/run");
  await expect(page.getByLabel(/回放/)).toBeDisabled();
  const r = await page.request.post("/api/pipeline-runs", {
    data: { security_ids: ["sec_nvda"], target_ids: ["regular_60m"], mode: "replay", as_of: "2026-12-01T15:00:00Z" },
  });
  expect(r.status()).toBe(403);
  const bad = await page.request.post("/api/pipeline-runs", { data: { security_ids: ["NVDA"], target_ids: ["regular_60m"] } });
  expect(bad.status()).toBe(400);
});
