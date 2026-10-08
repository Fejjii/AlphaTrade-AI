import { expect, test } from "@playwright/test";

// Browser fixtures prove presentation and request behavior; they are not venue evidence.
for (const width of [1280, 390]) {
  test(`demo account refresh stays separate from paper metrics at ${width}px`, async ({
    page, baseURL,
  }) => {
    let reads = 0;
    let refreshes = 0;
    let authenticated = false;
    let failRefresh = false;
    let fixtureNow = Date.now();
    await page.clock.install({ time: new Date(fixtureNow) });
    const snapshot = {
      venue: "BLOFIN_DEMO",
      read_only: true,
      status: "ok",
      can_refresh: true,
      snapshot_id: "browser-fixture",
      synced_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 300_000).toISOString(),
      total_equity_usd: "1001.50",
      refresh_error: null,
      last_attempt_at: null,
      balances: [{ asset: "USDT", total: "1000.25", available: "900.125", equity: "1002.25" }],
      positions: [
        {
          symbol: "BTCUSDT",
          side: "long",
          contracts: "0.1",
          base_asset: "BTC",
          base_quantity: "0.0001",
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
          url: baseURL!,
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
      if (url.origin === new URL(baseURL!).origin) return route.continue();
      const path = url.pathname;
      let body: unknown;
      if (path === "/health") {
        body = {
          execution_mode: "paper",
          real_trading_enabled: false,
          must_verify_email: false,
        };
      } else if (path === "/auth/me") {
        expect(route.request().headers().authorization).toBe("Bearer browser-fixture-token");
        authenticated = true;
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
        expect(route.request().method()).toBe("GET");
        expect(route.request().headers().authorization).toBe("Bearer browser-fixture-token");
        reads += 1;
        body = snapshot;
      } else if (path === "/dashboard/demo-account/refresh") {
        expect(route.request().method()).toBe("POST");
        expect(route.request().headers().authorization).toBe("Bearer browser-fixture-token");
        refreshes += 1;
        if (failRefresh) return route.fulfill({
          status: 503, json: { detail: "Fixture venue unavailable" },
          headers: { "Access-Control-Allow-Origin": "*" },
        });
        body = {
          ...snapshot, positions: [], position_count: 0,
          synced_at: new Date(fixtureNow).toISOString(),
          expires_at: new Date(fixtureNow + 300_000).toISOString(),
        };
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
    await expect(page).toHaveURL(new URL("/", baseURL!).href);
    const card = page.getByTestId("dashboard-demo-account");
    await expect(card).toContainText("0.1 contracts");
    await expect(card).toContainText("Unrealized PnL —");
    expect(authenticated).toBe(true);
    expect(reads).toBeGreaterThan(0);
    await expect(card).toContainText("1001.50 USD");
    await expect(card).toContainText("Equity: 1002.25 USDT");
    await expect(card).toContainText("Base quantity: 0.0001 BTC");
    expect(refreshes).toBe(0);
    const initialReads = reads;
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect.poll(() => reads).toBeGreaterThan(initialReads);
    expect(refreshes).toBe(0);
    // Exercise real browser timers and transport errors; values must survive.
    failRefresh = true;
    fixtureNow += 180_000;
    await page.clock.fastForward(180_000);
    await expect(card.getByRole("alert")).toContainText("refresh failed");
    await expect(card).toContainText("Stale snapshot");
    await expect(card).toContainText("0.1 contracts");
    expect(refreshes).toBe(1);
    fixtureNow += 180_000;
    await page.clock.fastForward(180_000);
    expect(refreshes).toBe(1); // Failure doubles the automatic retry interval.
    failRefresh = false;
    await card.getByRole("button", { name: "Refresh demo account" }).click();
    await expect(card).toContainText(
      "No native open positions at this snapshot.",
    );
    expect(refreshes).toBe(2);
    await expect(card).toContainText("Fresh snapshot");
    await expect(card.getByRole("alert")).toHaveCount(0);
    fixtureNow += 180_000;
    await page.clock.fastForward(180_000);
    await expect.poll(() => refreshes).toBe(3);
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
