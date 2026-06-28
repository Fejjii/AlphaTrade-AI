import { expect, test } from "@playwright/test";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "https://alphatrade-api-staging.onrender.com";
const DEMO_EMAIL = process.env.STAGING_DEMO_EMAIL ?? "demo@alphatrade.ai";
const DEMO_PASSWORD = process.env.STAGING_DEMO_PASSWORD ?? "";

test.describe("Staging setup alert review smoke (Slice 77)", () => {
  test.skip(
    process.env.PLAYWRIGHT_STAGING_REVIEW_SMOKE !== "1",
    "Set PLAYWRIGHT_STAGING_REVIEW_SMOKE=1 for staging review browser smoke",
  );

  test("review page, dashboard card, save persists — no Telegram or orders", async ({
    page,
    request,
  }) => {
    let accessToken: string;

    if (DEMO_PASSWORD) {
      const login = await request.post(`${API_URL}/auth/login`, {
        data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
      });
      expect(login.ok()).toBeTruthy();
      const auth = await login.json();
      accessToken = auth.tokens.access_token as string;
    } else {
      const email = `slice77-browser-${Date.now()}@example.com`;
      const password = "SecurePass123!Slice77Browser";
      const register = await request.post(`${API_URL}/auth/register`, {
        data: {
          email,
          password,
          organization_name: `Slice77 Browser ${Date.now()}`,
        },
      });
      expect(register.status()).toBe(201);
      const auth = await register.json();
      accessToken = auth.tokens.access_token as string;

      const scan = await request.post(`${API_URL}/market-watcher/scan`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        data: {
          confirm: "RUN_READ_ONLY_SCAN",
          create_in_app_alerts_confirm: "CREATE_IN_APP_ALERTS_ONLY",
          symbols: ["BTCUSDT", "ETHUSDT"],
          timeframes: ["15m", "1h"],
          dry_run: false,
        },
      });
      expect(scan.ok()).toBeTruthy();
    }

    const list = await request.get(`${API_URL}/alerts/setup-review?limit=5`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(list.ok()).toBeTruthy();
    const listBody = await list.json();
    const items = (listBody.items ?? []) as Array<{ alert_id: string }>;
    expect(items.length).toBeGreaterThan(0);

    const summary = await request.get(`${API_URL}/alerts/setup-review/summary`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(summary.ok()).toBeTruthy();

    await page.addInitScript((token: string) => {
      sessionStorage.setItem("alphatrade_access_token", token);
    }, accessToken);

    await page.goto("/alerts/review");
    await expect(page.getByTestId("setup-alert-review-page")).toBeVisible();
    await expect(page.getByText("Setup Alert Review")).toBeVisible();
    await expect(page.getByTestId("setup-alert-review-filters")).toBeVisible();
    await expect(page.getByTestId("setup-alert-review-summary")).toBeVisible();
    await expect(page.getByTestId("setup-alert-review-list")).toBeVisible();
    await expect(page.getByTestId("setup-alert-condition").first()).toBeVisible();
    await expect(page.getByTestId("setup-alert-confidence").first()).toBeVisible();
    await expect(page.getByTestId("setup-alert-trigger").first()).toBeVisible();
    await expect(page.getByTestId("setup-alert-invalidation").first()).toBeVisible();
    await expect(page.getByTestId("setup-alert-latest-price").first()).toBeVisible();
    await expect(page.getByTestId("setup-alert-review-status").first()).toBeVisible();
    await expect(page.getByTestId("setup-alert-notes").first()).toBeVisible();
    await expect(page.getByTestId("quick-action-watching").first()).toBeVisible();
    await expect(page.getByTestId("quick-action-important").first()).toBeVisible();
    await expect(page.getByTestId("quick-action-ignore").first()).toBeVisible();

    await expect(page.getByText(/send to telegram/i)).toHaveCount(0);
    await expect(page.getByText(/place order/i)).toHaveCount(0);
    await expect(page.getByText(/execute live/i)).toHaveCount(0);

    const targetAlertId = items[0].alert_id;
    const notes = `Slice77 browser smoke ${Date.now()}`;
    const card = page.getByTestId(`setup-alert-${targetAlertId}`);
    await card.getByTestId("setup-alert-review-status").selectOption("watching");
    await card.getByTestId("setup-alert-notes").fill(notes);
    await card.getByTestId("setup-alert-save").click();
    await expect(page.getByTestId("setup-alert-action-message")).toContainText(
      /review saved/i,
    );

    await page.reload();
    await expect(page.getByTestId(`setup-alert-${targetAlertId}`)).toBeVisible();
    const reloadedCard = page.getByTestId(`setup-alert-${targetAlertId}`);
    await expect(reloadedCard.getByTestId("setup-alert-review-status")).toHaveValue("watching");
    await expect(reloadedCard.getByTestId("setup-alert-notes")).toHaveValue(notes);

    await page.goto("/");
    await expect(page.getByTestId("dashboard-setup-alerts-review")).toBeVisible();
    await expect(page.getByText(/unreviewed:/i)).toBeVisible();
    await expect(page.getByText(/watching:/i)).toBeVisible();
    await expect(page.getByText(/important:/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /review setup alerts/i })).toBeVisible();
    await page.getByRole("link", { name: /review setup alerts/i }).click();
    await expect(page).toHaveURL(/\/alerts\/review/);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/bot\d{8,}:/i);
    expect(bodyText.toLowerCase()).not.toContain("telegram_bot_token");
    expect(bodyText.toLowerCase()).not.toContain("postgresql");
    expect(bodyText.toLowerCase()).not.toContain("rediss://");
  });
});
