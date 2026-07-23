import { expect, test } from "@playwright/test";

import { installSmokeSession } from "./helpers/staging-smoke-auth";

import {
  STAGING_API_URL,
  assertNonPlannedStartBlocked,
  findOrCreateSecondPlannedPlan,
  loginBootstrapOwner,
  START_RUN,
} from "./helpers/staging-run-sessions";

test.describe("Staging paper run sessions smoke (Slice 82)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_RUN_SESSION_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_RUN_SESSION_SMOKE=1 for staging run session browser smoke",
  );

  test("run sessions UI, plan start flow, non-planned blocked — no Telegram or orders", async ({
    page,
    request,
  }) => {
    const health = await request.get(`${STAGING_API_URL}/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = await health.json();
    expect(healthBody.execution_mode).toBe("paper");
    expect(healthBody.real_trading_enabled).toBe(false);
    if (healthBody.git_sha) {
      expect(String(healthBody.git_sha).length).toBeGreaterThanOrEqual(7);
    }

    const { accessToken } = await loginBootstrapOwner(request);

    const plans = await request.get(`${STAGING_API_URL}/paper-validation/run-plans?limit=50`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(plans.ok()).toBeTruthy();
    const plannedItems = ((await plans.json()).items ?? []).filter(
      (item: { plan_status: string }) => item.plan_status === "planned",
    );
    expect(plannedItems.length).toBeGreaterThan(0);
    const planId = plannedItems[0].plan_id as string;

    const secondPlanId = await findOrCreateSecondPlannedPlan(request, accessToken, planId);
    await assertNonPlannedStartBlocked(request, accessToken, secondPlanId);

    await installSmokeSession(page, accessToken);

    await page.goto("/paper-validation/run-plans");
    await expect(page.getByTestId("paper-validation-run-plans-page")).toBeVisible();

    await page.goto(`/paper-validation/run-plans/${planId}`);
    await expect(page.getByTestId("paper-validation-run-plan-detail")).toBeVisible();
    await expect(page.getByTestId("paper-run-plan-safety-copy")).toContainText(
      "No order. No proposal. No approval. No Telegram.",
    );
    await expect(page.getByTestId("paper-run-plan-start-section")).toBeVisible();
    await expect(page.getByTestId("paper-run-session-safety-copy")).toContainText(
      "Record only. No live run.",
    );

    await page.getByTestId("paper-run-session-confirm").fill(START_RUN);
    await page.getByTestId("paper-run-session-submit").click();
    await expect(page.getByTestId("paper-run-session-link")).toBeVisible({ timeout: 30_000 });
    const sessionHref = await page.getByTestId("paper-run-session-link").getAttribute("href");
    expect(sessionHref).toMatch(/\/paper-validation\/run-sessions\//);

    await page.goto("/paper-validation/run-sessions");
    await expect(page.getByTestId("paper-validation-run-sessions-page")).toBeVisible();
    await expect(page.getByText(/record only/i)).toBeVisible();
    await expect(page.getByTestId("paper-validation-run-sessions-list")).toBeVisible();

    await page.goto(sessionHref!);
    await expect(page.getByTestId("paper-validation-run-session-detail")).toBeVisible();
    await expect(page.getByTestId("paper-run-session-safety-copy")).toContainText(
      "No order. No exchange.",
    );

    await expect(page.getByText(/send to telegram/i)).toHaveCount(0);
    await expect(page.getByText(/place order/i)).toHaveCount(0);
    await expect(page.getByText(/execute live/i)).toHaveCount(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("postgresql");
    expect(bodyText.toLowerCase()).not.toContain("rediss://");
  });
});
