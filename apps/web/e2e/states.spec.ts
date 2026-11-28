// Five page states (DP 2.15, "正常、加载、空、超时、失败") with screenshots. SYNTHETIC fixture data.
import { expect, test } from "@playwright/test";

const shot = (name: string) => ({ path: `test-results/screens/${name}.png`, fullPage: true });

test("normal: monitor shows the four pilot securities @mobile", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByTestId("synthetic-banner")).toBeVisible();
  for (const t of ["NVDA", "AMD", "AVGO", "MU"]) await expect(page.getByTestId(`card-${t}`)).toBeVisible();
  await expect(page.getByTestId("card-MU").getByTestId("quality-stale")).toContainText("最近有效");
  await page.screenshot(shot(`monitor-normal-${info.project.name}`));
});

test("loading: a slow source shows the loading state first", async ({ page }) => {
  const nav = page.goto("/?state=slow");
  await expect(page.getByTestId("state-loading")).toBeVisible();
  await page.screenshot(shot("monitor-loading"));
  await nav;
  await expect(page.getByTestId("monitor-grid")).toBeVisible();
});

test("empty", async ({ page }) => {
  await page.goto("/?state=empty");
  await expect(page.getByTestId("state-empty")).toBeVisible();
  await page.screenshot(shot("monitor-empty"));
  await page.goto("/predictions?state=empty");
  await expect(page.getByTestId("state-empty")).toBeVisible();
});

test("timeout: says so and offers a retry", async ({ page }) => {
  await page.goto("/?state=timeout");
  const s = page.getByTestId("state-timeout");
  await expect(s).toContainText("加载超时");
  await expect(s.getByRole("link", { name: "重试" })).toHaveAttribute("href", "/");
  await page.screenshot(shot("monitor-timeout"));
});

test("failure", async ({ page }) => {
  await page.goto("/events?state=error");
  await expect(page.getByTestId("state-error")).toContainText("加载失败");
  await page.screenshot(shot("events-error"));
});

test("detail, predictions and events pages render", async ({ page }) => {
  await page.goto("/stock/NVDA");
  await expect(page.getByRole("heading", { name: /NVDA/ })).toBeVisible();
  await expect(page.getByTestId("run-button")).toBeVisible();
  await page.goto("/predictions");
  await expect(page.getByTestId("predictions-table")).toContainText("pred_nvda_20261201_1520_60m");
  await page.getByRole("link", { name: "pred_nvda_20261201_1520_60m" }).first().click();
  await expect(page.getByText("报告版")).toBeVisible();
  await page.goto("/events");
  await page.getByRole("link", { name: "policy:BIS:demo-2026-12345" }).click();
  await expect(page.getByText("regulated_party").first()).toBeVisible();
  await page.goto("/stock/ZZZZ"); // streamed page: the not-found view, not a 404 status (loading.tsx boundary)
  await expect(page.getByTestId("not-found")).toBeVisible();
  expect((await page.request.get("/api/predictions/pred_missing")).status()).toBe(404);
});
