import { expect, test } from "@playwright/test";

import { installSmokeSession, obtainPortfolioSmokeAccessToken } from "./helpers/staging-smoke-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

test.describe("Staging /portfolio read-only smoke (Slice 91B)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_PORTFOLIO_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_PORTFOLIO_SMOKE=1 for staging browser smoke",
  );

  test("portfolio page loads, shows safety copy, exposes no secrets or order/automation UI", async ({
    page,
    request,
  }) => {
    const { accessToken, loginStatus } = await obtainPortfolioSmokeAccessToken(request, API_URL);
    if (loginStatus !== null) {
      console.log(`POST /auth/login — HTTP ${loginStatus}`);
    }

    await installSmokeSession(page, accessToken);

    await page.goto("/portfolio");

    await expect(page.getByTestId("paper-portfolio-page")).toBeVisible();
    const safetyBanner = page.getByTestId("paper-portfolio-safety-banner");
    await expect(safetyBanner).toBeVisible();
    await expect(page.getByTestId("paper-portfolio-summary-cards")).toBeVisible();
    await expect(safetyBanner.getByTestId("paper-portfolio-paper-only")).toBeVisible();
    await expect(safetyBanner.getByText(/not live trading/i)).toBeVisible();
    await expect(
      safetyBanner.getByText(
        "Not investment advice. Does not indicate readiness for real money.",
        { exact: true },
      ),
    ).toBeVisible();

    const portfolio = await request.get(`${API_URL}/performance/portfolio`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(portfolio.ok()).toBeTruthy();
    const portfolioBody = await portfolio.json();
    expect(portfolioBody.safety.paper_only).toBe(true);
    expect(portfolioBody.safety.real_trading_enabled).toBe(false);

    const snapshots = await request.get(`${API_URL}/performance/snapshots`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(snapshots.ok()).toBeTruthy();

    await expect(page.getByRole("button", { name: /place order/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /execute/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /buy now/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /enable live trading/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /start automation/i })).toHaveCount(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/bot\d{8,}:/i);
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("jwt_secret");
  });
});
