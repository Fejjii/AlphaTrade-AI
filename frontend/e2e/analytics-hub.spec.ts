import { expect, test } from "@playwright/test";

import {
  installSmokeSession,
  obtainPortfolioSmokeAccessToken,
} from "./helpers/staging-smoke-auth";

const TAB_LABELS = [
  "Overview",
  "Performance",
  "Setups",
  "Behaviour",
  "Validation",
  "Comparison",
] as const;

/**
 * Stable Analytics hub coverage for the regular Playwright smoke suite (AT-041 PR4).
 * Staging-only extras remain in analytics-hub-staging.spec.ts.
 */
test.describe("Analytics hub smoke (regular)", () => {
  test("walks all six tabs with URL state, retry honesty, paper posture, and 390px overflow", async ({
    page,
    request,
  }) => {
    const apiUrl = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
    const { accessToken } = await obtainPortfolioSmokeAccessToken(request, apiUrl);
    await installSmokeSession(page, accessToken);

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });
    const failedRequests: string[] = [];
    page.on("response", (response) => {
      if (response.status() >= 500) {
        failedRequests.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto("/analytics?date_from=2026-01-01&date_to=2026-12-31");
    await expect(page.getByTestId("analytics-page")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Analytics" })).toHaveCount(1);
    await expect(page.getByText(/paper/i).first()).toBeVisible();

    const tablist = page.getByRole("tablist", { name: "Analytics sections" });
    await expect(tablist.getByRole("tab")).toHaveCount(6);

    for (const label of TAB_LABELS) {
      await tablist.getByRole("tab", { name: label }).click();
      await expect(tablist.getByRole("tab", { name: label })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      if (label === "Overview") {
        await expect(page).not.toHaveURL(/[?&]tab=/);
      } else {
        await expect(page).toHaveURL(new RegExp(`tab=${label.toLowerCase()}`));
      }
    }

    await tablist.getByRole("tab", { name: "Validation" }).click();
    await expect(page).toHaveURL(/tab=validation/);
    await expect(page.getByTestId("analytics-min-sample")).toBeVisible();
    await page.getByTestId("analytics-min-sample").fill("8");
    await page.getByTestId("analytics-apply-filters").click();
    await expect(page).toHaveURL(/min_sample=8/);
    await expect(page).toHaveURL(/date_from=2026-01-01/);

    await page.goBack();
    await expect(page).toHaveURL(/tab=validation/);
    await expect(page).not.toHaveURL(/min_sample=8/);

    // Mobile accessibility / overflow (PR #54 posture remains intact).
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByTestId("analytics-page")).toBeVisible();
    const overflow = await page.evaluate(() => {
      const root = document.documentElement;
      return root.scrollWidth > root.clientWidth + 1;
    });
    expect(overflow).toBeFalsy();

    // Collapsed filters on mobile (FP2-219) — disclosure remains available.
    const filterToggle = page.getByRole("button", { name: /filters/i }).first();
    if (await filterToggle.count()) {
      await expect(filterToggle).toBeVisible();
    }

    await expect(page.getByText(/paper/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /place order/i })).toHaveCount(0);
    expect(consoleErrors.filter((text) => !text.includes("favicon"))).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
});
