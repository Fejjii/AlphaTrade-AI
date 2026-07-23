import { expect, test } from "@playwright/test";

import { installSmokeSession } from "./helpers/staging-smoke-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging /learning-analytics read-only smoke (Slice 84)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_LEARNING_ANALYTICS_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_LEARNING_ANALYTICS_SMOKE=1 for staging browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("dashboard loads, shows safety copy, exposes no secrets or order/automation UI", async ({
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

    await page.goto("/learning-analytics");

    await expect(page.getByTestId("learning-analytics-page")).toBeVisible();
    await expect(page.getByTestId("learning-outcome-rates-card")).toBeVisible();
    await expect(page.getByTestId("learning-behavior-insights-card")).toBeVisible();
    await expect(page.getByTestId("learning-setup-ranking")).toBeVisible();
    await expect(page.getByText(/no orders, no/i)).toBeVisible();

    // Read-only API endpoints respond.
    const summary = await request.get(`${API_URL}/learning-analytics/summary`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(summary.ok()).toBeTruthy();

    // Ranking is explicitly non-automating.
    const ranking = await request.get(`${API_URL}/learning-analytics/setup-ranking`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(ranking.ok()).toBeTruthy();
    const rankingBody = await ranking.json();
    expect(String(rankingBody.note).toLowerCase()).toContain("automation");

    // No order/execution/automation controls, and no secrets leaked.
    await expect(page.getByRole("button", { name: /place order/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /execute/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /start run/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /automate/i })).toHaveCount(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/bot\d{8,}:/i);
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("jwt_secret");
  });
});
