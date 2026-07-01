import { expect, test } from "@playwright/test";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging /validation-priority read-only smoke (Slice 85)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_VALIDATION_PRIORITY_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_VALIDATION_PRIORITY_SMOKE=1 for staging browser smoke",
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

    await page.addInitScript((token: string) => {
      sessionStorage.setItem("alphatrade_access_token", token);
    }, accessToken);

    await page.goto("/validation-priority");

    await expect(page.getByTestId("validation-priority-page")).toBeVisible();
    await expect(page.getByTestId("validation-priority-summary")).toBeVisible();
    await expect(page.getByText(/no orders, no proposals, no automation/i)).toBeVisible();

    // Read-only API endpoints respond and stay non-automating.
    const queue = await request.get(`${API_URL}/validation-priority/queue`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(queue.ok()).toBeTruthy();
    const queueBody = await queue.json();
    expect(String(queueBody.note).toLowerCase()).toContain("automation");

    const summary = await request.get(`${API_URL}/validation-priority/summary`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(summary.ok()).toBeTruthy();

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
