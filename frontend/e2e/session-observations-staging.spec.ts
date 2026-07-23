import { expect, test } from "@playwright/test";

import { installSmokeSession } from "./helpers/staging-smoke-auth";

import {
  STAGING_API_URL,
  loginBootstrapOwner,
  START_RUN,
} from "./helpers/staging-run-sessions";

const RECORD_OBS = "RECORD_PAPER_VALIDATION_OBSERVATION";
const RECORD_OUTCOME = "RECORD_PAPER_VALIDATION_OUTCOME";

test.describe("Staging paper session observations smoke (Slice 83)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_OBSERVATION_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_OBSERVATION_SMOKE=1 for staging observation browser smoke",
  );

  test("session detail records observation and outcome — no Telegram or orders", async ({
    page,
    request,
  }) => {
    const health = await request.get(`${STAGING_API_URL}/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = await health.json();
    expect(healthBody.execution_mode).toBe("paper");
    expect(healthBody.real_trading_enabled).toBe(false);

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

    const start = await request.post(
      `${STAGING_API_URL}/paper-validation/run-plans/${planId}/start`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        data: { confirm: START_RUN, notes: "observation smoke" },
      },
    );
    expect(start.ok()).toBeTruthy();
    const sessionId = (await start.json()).session.session_id as string;

    await installSmokeSession(page, accessToken);

    await page.goto(`/paper-validation/run-sessions/${sessionId}`);
    await expect(page.getByTestId("paper-validation-run-session-detail")).toBeVisible();
    await expect(page.getByTestId("paper-run-session-safety-copy")).toContainText(
      "No order. No exchange.",
    );
    await expect(page.getByTestId("paper-run-session-observations")).toBeVisible();
    await expect(page.getByTestId("paper-run-session-result")).toBeVisible();

    await page.getByTestId("paper-run-session-observation-confirm").fill(RECORD_OBS);
    await page.getByTestId("paper-run-session-observation-submit").click();
    await expect(page.getByTestId("paper-run-session-observation-item")).toBeVisible({
      timeout: 30_000,
    });

    await page.getByTestId("paper-run-session-result-confirm").fill(RECORD_OUTCOME);
    await page.getByTestId("paper-run-session-result-submit").click();
    await expect(page.getByTestId("paper-run-session-result-summary")).toBeVisible({
      timeout: 30_000,
    });

    await expect(page.getByTestId("paper-run-session-mark-completed")).toBeEnabled();
    await expect(page.getByText(/send to telegram/i)).toHaveCount(0);
    await expect(page.getByText(/place order/i)).toHaveCount(0);
    await expect(page.getByText(/execute live/i)).toHaveCount(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("postgresql");
    expect(bodyText.toLowerCase()).not.toContain("rediss://");
  });
});
