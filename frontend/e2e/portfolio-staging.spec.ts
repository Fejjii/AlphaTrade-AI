import { expect, test } from "@playwright/test";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging /portfolio read-only smoke (Slice 91B)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_PORTFOLIO_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_PORTFOLIO_SMOKE=1 for staging browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("portfolio page loads, shows safety copy, exposes no secrets or order/automation UI", async ({
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

    await page.goto("/portfolio");

    await expect(page.getByTestId("paper-portfolio-page")).toBeVisible();
    await expect(page.getByTestId("paper-portfolio-safety-banner")).toBeVisible();
    await expect(page.getByTestId("paper-portfolio-summary-cards")).toBeVisible();
    await expect(page.getByText(/paper-only simulated portfolio/i)).toBeVisible();
    await expect(page.getByText(/not live trading/i)).toBeVisible();
    await expect(page.getByText(/not investment advice/i)).toBeVisible();

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
