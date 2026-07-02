import { expect, test } from "@playwright/test";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging /lessons read-only smoke (Slice 90B)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_LESSONS_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_LESSONS_SMOKE=1 for staging lessons browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("page loads, coaching filter works, no unsafe CTAs or secrets", async ({
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

    await page.goto("/lessons");

    await expect(page.getByTestId("lessons-page")).toBeVisible();
    await expect(page.getByText(/paper mode only/i)).toBeVisible();
    await expect(page.getByTestId("lessons-source-filter")).toBeVisible();

    await page.getByTestId("lessons-source-coaching").click();
    await expect(page.getByTestId("lessons-source-coaching")).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    const pending = await request.get(
      `${API_URL}/lessons/candidates?status=pending_review`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    expect(pending.ok()).toBeTruthy();

    const accepted = await request.get(`${API_URL}/lessons/accepted`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(accepted.ok()).toBeTruthy();

    await expect(page.getByRole("button", { name: /place order/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /execute/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /automate/i })).toHaveCount(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/bot\d{8,}:/i);
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("jwt_secret");
  });
});
