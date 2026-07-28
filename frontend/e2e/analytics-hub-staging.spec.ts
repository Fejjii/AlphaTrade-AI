import { expect, test } from "@playwright/test";

import { installSmokeSession } from "./helpers/staging-smoke-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

const TAB_LABELS = [
  "Overview",
  "Performance",
  "Setups",
  "Behaviour",
  "Validation",
  "Comparison",
] as const;

test.describe("Staging /analytics hub smoke (AT-040 PR4)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_ANALYTICS_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_ANALYTICS_SMOKE=1 for staging browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("walks all six tabs, Validation loading, filter persistence, and paper posture", async ({
    page,
    request,
  }) => {
    const login = await request.post(`${API_URL}/auth/login`, {
      data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const auth = await login.json();
    const accessToken = auth.tokens.access_token as string;

    await installSmokeSession(page, accessToken);

    await page.goto("/analytics?date_from=2026-01-01&date_to=2026-12-31");
    await expect(page.getByTestId("analytics-page")).toBeVisible();
    await expect(page.getByText(/paper/i).first()).toBeVisible();

    const tablist = page.getByRole("tablist", { name: "Analytics sections" });
    await expect(tablist.getByRole("tab")).toHaveCount(6);

    for (const label of TAB_LABELS) {
      await tablist.getByRole("tab", { name: label }).click();
      await expect(tablist.getByRole("tab", { name: label })).toHaveAttribute(
        "aria-selected",
        "true",
      );
    }

    await tablist.getByRole("tab", { name: "Validation" }).click();
    await expect(page).toHaveURL(/tab=validation/);
    await expect(page.getByTestId("validation-charts")).toBeVisible();
    await expect(page.getByTestId("analytics-min-sample")).toBeVisible();
    await expect(page.getByTestId("analytics-filter-summary")).toContainText("2026-01-01");

    await page.getByTestId("analytics-min-sample").fill("8");
    await page.getByTestId("analytics-apply-filters").click();
    await expect(page).toHaveURL(/min_sample=8/);
    await expect(page).toHaveURL(/date_from=2026-01-01/);

    await page.goBack();
    await expect(page).toHaveURL(/tab=validation/);
    await expect(page).not.toHaveURL(/min_sample=8/);

    await page.goForward();
    await expect(page).toHaveURL(/min_sample=8/);

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByTestId("analytics-page")).toBeVisible();
    await expect(page.getByTestId("validation-charts")).toBeVisible();

    const overflow = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollWidth > root.clientWidth + 1;
    });
    expect(overflow).toBeFalsy();

    await expect(page.getByText(/paper/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /place order/i })).toHaveCount(0);
  });
});
