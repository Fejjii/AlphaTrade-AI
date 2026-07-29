import { expect, test, type Route } from "@playwright/test";

import { installSharedE2ESession } from "./helpers/shared-e2e-auth";

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function isBackendApi(url: URL, pathPrefix: string): boolean {
  return url.port === "8000" && url.pathname.startsWith(pathPrefix);
}

test.describe("Deep-link contracts (AT-041 PR4)", () => {
  test.describe.configure({ mode: "serial" });

  test("valid analytics ?tab= resolves and invalid tab is cleaned without stale context", async ({
    page,
    request,
  }) => {
    await installSharedE2ESession(page, request);

    await page.goto("/analytics?tab=validation");
    await expect(page.getByTestId("analytics-page")).toBeVisible();
    await expect(page).toHaveURL(/tab=validation/);
    const tablist = page.getByRole("tablist", { name: "Analytics sections" });
    await expect(tablist.getByRole("tab", { name: "Validation" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.goto("/analytics?tab=not-a-real-tab");
    await expect(page.getByTestId("analytics-page")).toBeVisible();
    await expect(page.getByText(/Ignored invalid filter/i)).toBeVisible();
    await expect(page).not.toHaveURL(/tab=not-a-real-tab/);
  });

  test("invalid journal ?entry= shows limited-window notice and opens no unrelated entry", async ({
    page,
    request,
  }) => {
    await installSharedE2ESession(page, request);

    await page.route((url) => isBackendApi(url, "/journal/entries"), async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      await fulfillJson(route, {
        items: [
          {
            id: "entry-present",
            organization_id: "org",
            user_id: "user",
            symbol: "BTCUSDT",
            timeframe: "1h",
            direction: "long",
            entry_rationale: "Present entry",
            emotions: [],
            mistakes: [],
            result: "win",
            tags: [],
            screenshot_refs: [],
            created_at: "2026-07-21T12:00:00.000Z",
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      });
    });
    await page.route((url) => isBackendApi(url, "/positions"), async (route) => {
      await fulfillJson(route, { items: [], total: 0, limit: 50, offset: 0 });
    });

    await page.goto("/journal?entry=missing-entry-id");
    const journalNotice = page.getByTestId("journal-stale-entry");
    await expect(journalNotice).toBeVisible();
    await expect(journalNotice).toContainText(/most recent 50 journal entries/i);
    await expect(journalNotice).toContainText(/No unrelated entry was opened/i);
  });

  test("invalid knowledge ?document= shows limited-window notice", async ({ page, request }) => {
    await installSharedE2ESession(page, request);

    await page.route((url) => isBackendApi(url, "/knowledge"), async (route) => {
      await fulfillJson(route, {
        items: [],
        documents: [],
        chunks: [],
        total: 0,
        limit: 50,
        offset: 0,
      });
    });

    await page.goto("/knowledge?document=missing-document-id");
    const knowledgeNotice = page.getByTestId("knowledge-document-stale");
    await expect(knowledgeNotice).toBeVisible();
    await expect(knowledgeNotice).toContainText(/not found|limited|recent|window|loaded/i);
  });

  test("invalid tradingview ?signal= shows missing notice and clears without selecting another", async ({
    page,
    request,
  }) => {
    await installSharedE2ESession(page, request);

    await page.route((url) => isBackendApi(url, "/tradingview"), async (route) => {
      await fulfillJson(route, { items: [], total: 0, limit: 50, offset: 0 });
    });
    await page.route((url) => isBackendApi(url, "/alerts"), async (route) => {
      await fulfillJson(route, { items: [], total: 0, limit: 50, offset: 0 });
    });

    await page.goto("/tradingview-signals?signal=missing-signal-id");
    const signalNotice = page.getByTestId("signal-deep-link-missing");
    await expect(signalNotice).toBeVisible();
    await expect(signalNotice).toContainText(/requested signal not found/i);
    await expect(page.getByRole("button", { name: /clear stale link/i })).toBeVisible();
    await page.getByRole("button", { name: /clear stale link/i }).click();
    await expect(page).toHaveURL(/\/tradingview-signals$/);
    await expect(page).not.toHaveURL(/signal=/);
  });
});
