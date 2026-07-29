import { expect, test, type Route } from "@playwright/test";

import { installSharedE2ESession, paperModeActive } from "./helpers/shared-e2e-auth";

const OPEN_POSITION = {
  id: "pos-e2e-1",
  organization_id: "org-1",
  user_id: "user-1",
  symbol: "BTCUSDT",
  direction: "long",
  size: "0.25",
  entry_price: "50637.87",
  leverage: "1",
  stop_loss: null,
  take_profits: [],
  liquidation_price: null,
  unrealized_pnl: "12.5",
  realized_pnl: "0",
  risk_state: {},
  status: "open",
  opened_at: "2026-07-27T10:00:00.000Z",
  closed_at: null,
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.describe("Paper-close browser flow (AT-041 PR4 / FP2-001)", () => {
  test.describe.configure({ mode: "serial" });

  test("requires exit price, confirms, submits exact price, and never hits live exchange", async ({
    page,
    request,
  }) => {
    await installSharedE2ESession(page, request);

    let listCalls = 0;
    const closeBodies: unknown[] = [];
    const forbiddenPaths: string[] = [];

    await page.route("**/positions**", async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.pathname.includes("/close-paper") && req.method() === "POST") {
        closeBodies.push(req.postDataJSON());
        await fulfillJson(route, {
          ...OPEN_POSITION,
          status: "closed",
          closed_at: "2026-07-29T12:00:00.000Z",
        });
        return;
      }
      if (req.method() === "GET" && url.pathname.endsWith("/positions")) {
        listCalls += 1;
        const items = closeBodies.length ? [] : [OPEN_POSITION];
        await fulfillJson(route, { items, total: items.length, limit: 50, offset: 0 });
        return;
      }
      await route.continue();
    });

    await page.route("**/exchange/**", async (route) => {
      forbiddenPaths.push(route.request().url());
      await fulfillJson(route, { detail: "blocked in paper-close e2e" }, 500);
    });
    await page.route("**/execution/**", async (route) => {
      forbiddenPaths.push(route.request().url());
      await fulfillJson(route, { detail: "unexpected execution call" }, 500);
    });

    await page.goto("/positions");
    await expect(page.getByTestId("positions-page")).toBeVisible();
    await expect(page.getByText(/BTCUSDT/)).toBeVisible();
    await expect(paperModeActive(page)).toBeVisible();

    await page.getByTestId("close-paper-start").click();
    await page.getByTestId("close-paper-review").click();
    await expect(page.getByText(/positive number/i)).toBeVisible();
    expect(closeBodies).toHaveLength(0);

    await page.getByTestId("close-paper-exit-price").fill("51000.5");
    await page.getByTestId("close-paper-review").click();
    const confirmation = page.getByTestId("close-paper-confirmation");
    await expect(confirmation).toContainText("BTCUSDT");
    await expect(confirmation).toContainText("51000.5");

    await page.getByTestId("close-paper-confirm").click();
    await expect.poll(() => closeBodies.length).toBe(1);
    expect(closeBodies[0]).toMatchObject({
      exit_price: "51000.5",
      reason: "Paper close at user-entered exit price",
    });
    expect(forbiddenPaths).toEqual([]);
    await expect(page.getByTestId("empty-state")).toBeVisible({ timeout: 15_000 });
    expect(listCalls).toBeGreaterThan(1);
  });

  test("API failure leaves the position open and shows honest feedback", async ({
    page,
    request,
  }) => {
    await installSharedE2ESession(page, request);

    await page.route("**/positions**", async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.pathname.includes("/close-paper") && req.method() === "POST") {
        await fulfillJson(route, { detail: "Paper close rejected by risk engine" }, 400);
        return;
      }
      if (req.method() === "GET") {
        await fulfillJson(route, { items: [OPEN_POSITION], total: 1, limit: 50, offset: 0 });
        return;
      }
      await route.continue();
    });

    await page.goto("/positions");
    await expect(page.getByTestId("close-paper-start")).toBeVisible();
    await page.getByTestId("close-paper-start").click();
    await page.getByTestId("close-paper-exit-price").fill("51000.5");
    await page.getByTestId("close-paper-review").click();
    await page.getByTestId("close-paper-confirm").click();

    const alert = page.getByTestId("close-paper-error");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(/remains open/i);
    await expect(page.getByText(/BTCUSDT/)).toBeVisible();
    await expect(page.getByTestId("close-paper-confirmation")).toBeVisible();
  });
});
