import { expect, test } from "@playwright/test";

import { installSmokeSession, obtainPortfolioSmokeAccessToken } from "./helpers/staging-smoke-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

/**
 * Backend schema default disclaimer — mirrors
 * STANDARD_PAPER_PORTFOLIO_DISCLAIMER in PaperPortfolioSafetyBanner.tsx.
 */
const STANDARD_DISCLAIMER =
  "Paper-only simulated portfolio. Not investment advice. Does not indicate readiness for real money.";

type SafetyPayload = {
  execution_mode?: string | null;
  paper_only?: boolean;
  real_trading_enabled?: boolean;
  disclaimer?: string | null;
};

/**
 * FP2-123: the redundant portfolio safety banner is intentionally suppressed
 * when the payload confirms the standard verified paper posture — the global
 * StatusStrip and page-header PaperModeIndicator already communicate it.
 * Mirrors shouldSuppressPaperPortfolioSafetyBanner in PaperPortfolioSafetyBanner.tsx.
 */
function bannerSuppressed(safety: SafetyPayload): boolean {
  return (
    (safety.execution_mode ?? "").trim().toLowerCase() === "paper" &&
    safety.paper_only === true &&
    safety.real_trading_enabled === false &&
    (safety.disclaimer ?? "").replace(/\s+/g, " ").trim() === STANDARD_DISCLAIMER
  );
}

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
    await expect(page.getByTestId("paper-portfolio-summary-cards")).toBeVisible();

    const portfolio = await request.get(`${API_URL}/performance/portfolio`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(portfolio.ok()).toBeTruthy();
    const portfolioBody = await portfolio.json();
    expect(portfolioBody.safety.paper_only).toBe(true);
    expect(portfolioBody.safety.real_trading_enabled).toBe(false);

    const safetyBanner = page.getByTestId("paper-portfolio-safety-banner");
    if (bannerSuppressed(portfolioBody.safety)) {
      // Verified standard paper posture: the redundant banner is suppressed
      // (FP2-123); the retained surfaces must still communicate paper safety.
      await expect(safetyBanner).toHaveCount(0);
      await expect(page.getByTestId("status-strip")).toBeVisible();
      await expect(page.getByTestId("paper-mode-indicator").first()).toBeVisible();
      await expect(
        page.getByTestId("paper-mode-indicator").filter({ hasText: /paper/i }).first(),
      ).toBeVisible();
      await expect(page.getByText(/no live trading/i).first()).toBeVisible();
    } else {
      // Unverified, live, conflicting, or dynamic-disclaimer states must keep
      // the banner visible.
      await expect(safetyBanner).toBeVisible();
      await expect(safetyBanner.getByTestId("paper-portfolio-paper-only")).toBeVisible();
      await expect(
        safetyBanner.getByText(
          "Not investment advice. Does not indicate readiness for real money.",
          { exact: true },
        ),
      ).toBeVisible();
    }

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
