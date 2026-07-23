import { expect, test } from "@playwright/test";

import { installSmokeSession } from "./helpers/staging-smoke-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "https://alphatrade-api-staging.onrender.com";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging paper draft smoke (Slice 78)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_DRAFT_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_DRAFT_SMOKE=1 for staging draft browser smoke",
  );

  test.skip(!DEMO_PASSWORD, "STAGING_DEMO_PASSWORD required");

  test("review draft flow, drafts list, dashboard card — no Telegram or orders", async ({
    page,
    request,
  }) => {
    const login = await request.post(`${API_URL}/auth/login`, {
      data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const auth = await login.json();
    const accessToken = auth.tokens.access_token as string;

    const list = await request.get(`${API_URL}/alerts/setup-review?limit=5`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(list.ok()).toBeTruthy();
    const items = ((await list.json()).items ?? []) as Array<{ alert_id: string }>;
    expect(items.length).toBeGreaterThan(0);

    const targetAlertId = items[0].alert_id;
    await request.patch(`${API_URL}/alerts/setup-review/${targetAlertId}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: {
        review_status: "watching",
        review_notes: "Slice78 browser smoke",
      },
    });

    await installSmokeSession(page, accessToken);

    await page.goto("/alerts/review");
    await expect(page.getByTestId("setup-alert-review-page")).toBeVisible();

    const card = page.getByTestId(`setup-alert-${targetAlertId}`);
    await expect(card.getByTestId("setup-alert-create-draft")).toBeVisible();
    await card.getByTestId("setup-alert-create-draft").click();
    await expect(card.getByTestId("setup-alert-draft-warning")).toContainText(
      "Draft only. No order. No Telegram. No execution.",
    );
    await card.getByTestId("setup-alert-draft-confirm").fill("CREATE_PAPER_VALIDATION_DRAFT");
    await card.getByTestId("setup-alert-draft-submit").click();
    await expect(card.getByTestId("setup-alert-draft-link")).toContainText(/view draft/i);

    await page.goto("/paper-validation/drafts");
    await expect(page.getByTestId("paper-validation-drafts-page")).toBeVisible();
    await expect(page.getByTestId("paper-validation-drafts-list")).toBeVisible();

    await page.goto("/");
    await expect(page.getByTestId("dashboard-paper-drafts")).toBeVisible();
    await expect(page.getByRole("link", { name: /view paper drafts/i })).toBeVisible();

    await expect(page.getByText(/send to telegram/i)).toHaveCount(0);
    await expect(page.getByText(/place order/i)).toHaveCount(0);
    await expect(page.getByText(/execute live/i)).toHaveCount(0);
  });
});
