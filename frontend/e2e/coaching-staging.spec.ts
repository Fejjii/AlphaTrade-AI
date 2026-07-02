import { expect, test } from "@playwright/test";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging /coaching smoke (Slice 87)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_COACHING_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_COACHING_SMOKE=1 for staging browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("coaching page loads with safe copy and no automation controls", async ({
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

    await page.goto("/coaching");

    await expect(page.getByTestId("coaching-page")).toBeVisible();
    await expect(page.getByText(/review this behavior/i)).toBeVisible();
    await expect(page.getByText(/no orders, no automation/i)).toBeVisible();

    const prompts = await request.get(`${API_URL}/coaching/prompts`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(prompts.ok()).toBeTruthy();
    const body = await prompts.json();
    expect(String(body.note).toLowerCase()).toContain("automation");

    await expect(page.getByRole("button", { name: /place order/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /execute/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /start run/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /automate/i })).toHaveCount(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("jwt_secret");
  });
});
