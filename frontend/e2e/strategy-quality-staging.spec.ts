import { expect, test } from "@playwright/test";

import { installSmokeSession } from "./helpers/staging-smoke-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging /strategy-quality read-only smoke (Slice 89)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_STRATEGY_QUALITY_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_STRATEGY_QUALITY_SMOKE=1 for staging browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("page loads, shows safety copy, exposes no secrets or order/automation UI", async ({
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

    await page.goto("/strategy-quality");

    await expect(page.getByTestId("strategy-quality-page")).toBeVisible();
    await expect(page.getByTestId("strategy-quality-summary")).toBeVisible();
    await expect(
      page.getByText(/does not change strategy rules, enable or disable detectors/i),
    ).toBeVisible();

    // Read-only API endpoints respond and stay non-automating.
    const detectors = await request.get(`${API_URL}/strategy-quality/detectors`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(detectors.ok()).toBeTruthy();
    const detectorsBody = await detectors.json();
    expect(String(detectorsBody.note).toLowerCase()).toContain("do not");

    const summary = await request.get(`${API_URL}/strategy-quality/summary`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(summary.ok()).toBeTruthy();

    // No order/execution/rule-change/automation controls, and no secrets leaked.
    await expect(page.getByRole("button", { name: /place order/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /execute/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /disable detector/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /change rule/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /automate/i })).toHaveCount(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/bot\d{8,}:/i);
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("jwt_secret");
  });
});
