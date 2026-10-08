import { expect, test } from "@playwright/test";

// Browser fixtures prove presentation and request behavior; they are not venue evidence.
for (const width of [1280, 390]) {
  test(`demo account refresh stays separate from paper metrics at ${width}px`, async ({
    page,
  }) => {
    let reads = 0;
    let refreshes = 0;
    const snapshot = {
      venue: "BLOFIN_DEMO",
      read_only: true,
      status: "ok",
      can_refresh: true,
      snapshot_id: "browser-fixture",
      synced_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 300_000).toISOString(),
      balances: [{ asset: "USDT", total: "1000.25", available: "900.125" }],
      positions: [
        {
          symbol: "BTCUSDT",
          side: "long",
          contracts: "0.1",
          entry_price: "82894",
          mark_price: "82895",
          unrealized_pnl: null,
          leverage: "1",
        },
      ],
      balances_truncated: false,
      positions_truncated: false,
      position_count: 1,
      message: "Native demo account snapshot.",
    };
    await page
      .context()
      .addCookies([
        {
          name: "alphatrade_session",
          value: "1",
          url: "http://127.0.0.1:3000",
        },
      ]);
    await page.addInitScript(() =>
      sessionStorage.setItem(
        "alphatrade_access_token",
        "browser-fixture-token",
      ),
    );
    await page.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.port === "3000") return route.continue();
      const path = url.pathname;
      let body: unknown;
      if (path === "/health") {
        body = {
          execution_mode: "paper",
          real_trading_enabled: false,
          must_verify_email: false,
        };
      } else if (path === "/auth/me") {
        body = {
          user: {
            id: "fixture-user",
            email: "fixture@example.com",
            email_verified: true,
            role: "owner",
          },
          organization: { id: "fixture-org", name: "Browser fixture" },
        };
      } else if (path === "/dashboard/demo-account") {
        reads += 1;
        body = snapshot;
      } else if (path === "/dashboard/demo-account/refresh") {
        expect(route.request().method()).toBe("POST");
        refreshes += 1;
        body = { ...snapshot, positions: [], position_count: 0 };
      } else if (path === "/dashboard/summary") {
        body = {
          safety: { execution_mode: "paper", real_trading_enabled: false },
          open_paper_trades_summary: { total_count: 0, items: [] },
        };
      } else if (path === "/performance/portfolio") {
        body = {
          account: { current_equity: "500.50" },
          metrics: { trade_count: 0, net_pnl: "12.50" },
          breakdowns: { by_strategy: [] },
        };
      } else if (path === "/providers/status") {
        body = { providers: [] };
      } else {
        return route.fulfill({
          status: 503,
          json: { detail: "Browser fixture source unavailable" },
          headers: { "Access-Control-Allow-Origin": "*" },
        });
      }
      return route.fulfill({
        json: body,
        headers: { "Access-Control-Allow-Origin": "*" },
      });
    });
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    const card = page.getByTestId("dashboard-demo-account");
    await expect(card).toContainText("0.1 contracts");
    await expect(card).toContainText("Unrealized PnL —");
    expect(refreshes).toBe(0);
    const initialReads = reads;
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect.poll(() => reads).toBeGreaterThan(initialReads);
    expect(refreshes).toBe(0);
    await card.getByRole("button", { name: "Refresh demo account" }).click();
    await expect(card).toContainText(
      "No native open positions at this snapshot.",
    );
    expect(refreshes).toBe(1);
    await expect(page.getByTestId("dashboard-equity")).toContainText("500.50");
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth + 1,
    );
    expect(overflow).toBe(false);
    await page.screenshot({
      path: `/tmp/blofin-dashboard-${width}.png`,
      fullPage: true,
    });
  });
}
