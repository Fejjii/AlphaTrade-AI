import { expect, test } from "@playwright/test";

import { getSharedE2EAccessToken, installSharedE2ESession, paperModeActive } from "./helpers/shared-e2e-auth";

async function hasHorizontalOverflow(page: import("@playwright/test").Page): Promise<boolean> {
  return page.evaluate(() => {
    const root = document.documentElement;
    return root.scrollWidth > root.clientWidth + 1;
  });
}

test.describe("Canonical paper decision workflow", () => {
  test("unauthenticated /decision redirects to login", async ({ page }) => {
    await page.goto("/decision");
    await expect(page).toHaveURL(/\/login\?next=%2Fdecision/);
  });

  test("hub, market, candidates, strategy: paper-only, one h1, no live execution", async ({
    page,
    request,
  }) => {
    await installSharedE2ESession(page, request);

    for (const route of ["/decision", "/decision/market", "/decision/candidates", "/decision/strategy"]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      expect(await page.getByRole("heading", { level: 1 }).count()).toBe(1);
      await expect(paperModeActive(page)).toBeVisible();
      await expect(page.getByTestId("decision-safety-rail")).toBeVisible();
      await expect(page.getByTestId("decision-human-approval-copy")).toBeVisible();
      await expect(page.getByTestId("decision-stepper")).toBeVisible();
      await expect(page.getByRole("button", { name: /place real order/i })).toHaveCount(0);
      await expect(page.getByRole("button", { name: /execute live/i })).toHaveCount(0);
    }

    await page.goto("/decision");
    await expect(page.getByRole("link", { name: /legacy ai assist/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /legacy approvals/i })).toBeVisible();
    await expect(page.getByText(/canonical candidate http is unbound/i)).toHaveCount(0);
  });

  test("canonical HTTP reads require auth and stay tenant-empty without seed", async ({
    request,
  }) => {
    const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
    const unauth = await request.get(`${apiURL}/canonical/candidates`);
    expect(unauth.status()).toBe(401);

    const health = await request.get(`${apiURL}/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = (await health.json()) as {
      execution_mode?: string;
      real_trading_enabled?: boolean;
      market_watcher_enabled?: boolean;
      telegram_alerts_enabled?: boolean;
      telegram_interaction_enabled?: boolean;
    };
    expect(healthBody.execution_mode).toBe("paper");
    expect(healthBody.real_trading_enabled).toBe(false);
    if (healthBody.market_watcher_enabled !== undefined) {
      expect(healthBody.market_watcher_enabled).toBe(false);
    }
    if (healthBody.telegram_alerts_enabled !== undefined) {
      expect(healthBody.telegram_alerts_enabled).toBe(false);
    }
    if (healthBody.telegram_interaction_enabled !== undefined) {
      expect(healthBody.telegram_interaction_enabled).toBe(false);
    }

    const token = await getSharedE2EAccessToken(request);
    const candidates = await request.get(`${apiURL}/canonical/candidates`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(candidates.ok(), `canonical candidates HTTP ${candidates.status()}`).toBeTruthy();
    const listed = (await candidates.json()) as { total: number };
    expect(listed.total).toBe(0);

    const stats = await request.get(`${apiURL}/canonical/learning/strategy-stats`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(stats.ok(), `strategy stats HTTP ${stats.status()}`).toBeTruthy();
  });

  test("iPhone-width decision hub does not overflow and keeps Plan in the bottom nav", async ({
    page,
    request,
  }) => {
    await installSharedE2ESession(page, request);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/decision");
    await expect(page.getByRole("heading", { level: 1, name: "Decision" })).toBeVisible();
    expect(await hasHorizontalOverflow(page)).toBeFalsy();
    const plan = page.getByTestId("mobile-bottom-navigation").getByRole("link", { name: "Plan" });
    await expect(plan).toHaveAttribute("href", "/decision");
    await expect(page.getByRole("banner").getByTestId("kill-switch-button")).toBeVisible();
    await expect(
      page.getByTestId("decision-safety-rail").getByTestId("kill-switch-button"),
    ).toBeVisible();
  });
});
