import { expect, test } from "@playwright/test";

import { installSmokeSession } from "./helpers/staging-smoke-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging /alerts read-only smoke (Slice 70)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_ALERTS_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_ALERTS_SMOKE=1 for staging browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("manual delivery panel, alerts, delivered state, confirmation gate, no secrets", async ({
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

    await page.goto("/alerts");
    await expect(page.getByTestId("telegram-manual-delivery-panel")).toBeVisible();
    await expect(page.getByText(/manual telegram delivery/i)).toBeVisible();
    await expect(page.getByText(/manual delivery only/i)).toBeVisible();

    const alertsResponse = await request.get(`${API_URL}/alerts?limit=50`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(alertsResponse.ok()).toBeTruthy();
    const alertsBody = await alertsResponse.json();
    const items = (alertsBody.items ?? []) as Array<{
      id: string;
      message: string;
      delivery_channel?: string;
      delivery_status?: string;
    }>;
    expect(items.length).toBeGreaterThan(0);

    const delivered = items.find(
      (a) => a.delivery_channel === "telegram" && a.delivery_status === "delivered",
    );
    expect(delivered, "expected at least one telegram-delivered alert on demo tenant").toBeTruthy();
    await expect(page.getByTestId("telegram-already-delivered").first()).toBeVisible();
    await expect(page.getByTestId("alerts-list")).toBeVisible();
    await expect(page.getByTestId("alert-card").first()).toBeVisible();

    const sendButtons = page.getByTestId("send-alert-telegram-button");
    if ((await sendButtons.count()) > 0) {
      await expect(sendButtons.first()).toBeDisabled();
      await page.getByTestId("telegram-alert-confirm-input").first().fill("DELIVER_TELEGRAM_ALERT");
      await expect(sendButtons.first()).toBeEnabled();
    }

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/bot\d{8,}:/i);
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
  });
});
