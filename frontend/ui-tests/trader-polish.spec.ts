import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

import type { JournalTradeStatsMetrics } from "../src/lib/api/types";
import { makeWatcherMonitoringSnapshot } from "../src/lib/watcher-monitoring-fixtures";

// Synthetic, frontend-only fixtures. These are never shown by the product at runtime.
const timestamp = "2026-10-01T09:00:00Z";
const metrics: JournalTradeStatsMetrics = {
  trade_count: 3,
  wins: 2,
  losses: 1,
  breakeven: 0,
  win_rate: 2 / 3,
  pnl_sample_count: 3,
  net_pnl_total: "25",
  gross_pnl_total: "28",
  expectancy: "8.33",
  average_winner: "20",
  average_loser: "-15",
  profit_factor: 2.67,
  r_sample_count: 0,
  average_r: null,
  cost_sample_count: 3,
  fees_total: "3",
  funding_total: "0",
  slippage_total: null,
  total_costs: "3",
  mfe_sample_count: 0,
  average_mfe_amount: null,
  mae_sample_count: 0,
  average_mae_amount: null,
  capture_sample_count: 0,
  available_profit_total: null,
  realized_on_available_total: null,
  average_realized_vs_available_pct: null,
  confidence: "insufficient",
  warnings: [
    {
      code: "insufficient_sample",
      message:
        "Only 3 closed trades; insufficient sample for reliable conclusions.",
    },
  ],
};
const entries = [
  {
    id: "fixture-entry",
    symbol: "BTCUSDT",
    timeframe: "1h",
    direction: "long",
    result: "win",
    entry_rationale:
      "Waited for the recorded higher-timeframe level to hold before entering.",
    lessons: "Keep the invalidation level explicit before entry.",
    mistakes: ["Late entry"],
    pnl: "20",
    strategy_id: "fixture-pullback",
    created_at: timestamp,
  },
];
const trades = [
  {
    id: "fixture-trade",
    symbol: "ETHUSDT",
    timeframe: "1h",
    direction: "short",
    result: "loss",
    status: "closed",
    thesis: "Expected a rejection at the recorded range high.",
    net_pnl: "-15",
    strategy_label: "Fixture pullback",
    entry_price: "2500",
    exit_price: "2515",
    fees: "1",
    exit_reason: "Stop loss",
  },
];
const paginated = (items: unknown[]) => ({
  items,
  total: items.length,
  limit: 30,
  offset: 0,
});

async function installFixtures(
  page: Page,
  mode: "populated" | "empty" | "failed" = "populated",
) {
  await page
    .context()
    .addCookies([
      { name: "alphatrade_session", value: "1", url: "http://127.0.0.1:3000" },
    ]);
  await page.addInitScript(() =>
    sessionStorage.setItem("alphatrade_access_token", "frontend-fixture-only"),
  );
  await page.route("http://localhost:8000/**", async (route) => {
    const url = new URL(route.request().url());
    // The consolidated Journal now reads the attention projection separately.
    // Its availability does not change the seeded Journal/portfolio records.
    if (["/dashboard/attention", "/dashboard/daily-review"].includes(url.pathname)) {
      await route.fulfill({ status: 503, json: { detail: "Attention unavailable in polish fixture" } });
      return;
    }
    const fixtureEntries = mode === "empty" ? [] : entries;
    const fixtureTrades = mode === "empty" ? [] : trades;
    const safety = {
      execution_mode: "paper",
      real_trading_enabled: false,
      paper_only: true,
    };
    const fixtures: Record<string, unknown> = {
      "/health": {
        ...safety,
        status: "ok",
        provider_mode: "mock",
        must_verify_email: false,
      },
      "/auth/me": {
        user: {
          id: "fixture-user",
          email: "fixture@example.com",
          email_verified: true,
        },
        organization: { id: "fixture-org", name: "Frontend fixture" },
      },
      "/providers/status": { providers: [] },
      "/risk/kill-switch": {
        active: false,
        global_active: false,
        execution_blocked: false,
      },
      "/performance/portfolio": {
        safety,
        account: { current_equity: "10025", as_of: timestamp },
        metrics: {
          trade_count: mode === "empty" ? 0 : 3,
          win_rate: 2 / 3,
          net_pnl: mode === "empty" ? "0" : "25",
          expectancy: mode === "empty" ? "0" : "8.33",
        },
        breakdowns: {
          by_strategy:
            mode === "empty"
              ? []
              : [
                  {
                    key: "Fixture pullback",
                    metrics: { net_pnl: "25", trade_count: 3 },
                  },
                ],
        },
      },
      "/positions": paginated(
        mode === "empty"
          ? []
          : [
              {
                id: "fixture-position",
                symbol: "BTCUSDT",
                direction: "long",
                entry_price: "60000",
                unrealized_pnl: null,
              },
            ],
      ),
      "/journal/entries": paginated(fixtureEntries),
      "/journal/trades": paginated(fixtureTrades),
      "/journal/statistics": {
        group_by: url.searchParams.get("group_by"),
        overall:
          mode === "empty"
            ? {
                ...metrics,
                trade_count: 0,
                wins: 0,
                losses: 0,
                pnl_sample_count: 0,
                win_rate: null,
                net_pnl_total: null,
                expectancy: null,
              }
            : metrics,
        buckets:
          mode === "empty"
            ? []
            : [{ key: "fixture", label: "Fixture pullback", metrics }],
        total_buckets: 1,
        max_rows: 5000,
        truncated: false,
      },
      "/dashboard/summary": {
        safety,
        daily_discipline: {
          date: "2026-10-01",
          timezone: "UTC",
          paper_trades_opened_today: 1,
          paper_trades_closed_today: 3,
          realized_pnl_today_paper: "25",
          remaining_trades_allowed: null,
          discipline_status: "caution",
          recommended_action:
            "Review the closed trades before considering another setup.",
          loss_lock_active: false,
          green_day_protection_active: false,
          overtrading_warning_active: true,
          reasons: ["Recorded trade count is near the daily limit."],
          limitations: ["Remaining trade allowance unavailable."],
        },
      },
      "/market-watcher/monitoring": makeWatcherMonitoringSnapshot(),
      "/canonical/market-status": {
        availability: "unavailable",
        symbol: "BTCUSDT",
      },
      "/alerts": paginated(
        mode === "empty"
          ? []
          : [
              {
                id: "fixture-alert",
                severity: "high",
                message:
                  "Review the daily trade limit before opening another paper position.",
                read_at: null,
                created_at: timestamp,
              },
            ],
      ),
      "/conversations": paginated(
        mode === "empty"
          ? []
          : [{ id: "fixture-conversation", title: "Review the paper trade" }],
      ),
      "/conversations/fixture-conversation/messages": paginated([
        {
          id: "fixture-user-message",
          role: "user",
          content: "What should I learn from this paper trade?",
          created_at: timestamp,
        },
        {
          id: "fixture-agent-message",
          role: "assistant",
          content:
            "Review the recorded thesis and invalidation. Market evidence is unavailable, so no current price or market conclusion is provided.\n\nKeep your lesson tied to the recorded decision.",
          created_at: timestamp,
        },
      ]),
      "/strategies": paginated([]),
      "/lessons/candidates": paginated(
        mode === "empty"
          ? []
          : [
              {
                id: "fixture-lesson",
                lesson_text: "Record invalidation before entry.",
                mistake_type: "late_entry",
                status: "pending",
              },
            ],
      ),
      "/coaching/prompts": {
        items:
          mode === "empty"
            ? []
            : [
                {
                  signature: "fixture-prompt",
                  prompt_text:
                    "Did you follow your recorded invalidation rule?",
                },
              ],
      },
    };
    const shellPaths = [
      "/health",
      "/auth/me",
      "/providers/status",
      "/risk/kill-switch",
    ];
    if (mode === "failed" && !shellPaths.includes(url.pathname)) {
      await route.fulfill({
        status: 503,
        json: { detail: "Fixture source unavailable" },
      });
    } else if (url.pathname in fixtures) {
      await route.fulfill({ json: fixtures[url.pathname] });
    } else {
      throw new Error(`Unexpected frontend API request: ${url.pathname}`);
    }
  });
}

async function expectFits(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  // AppShell clips horizontal overflow; inspect children too so clipping cannot hide broken rows.
  const clipped = await page.locator("#main").evaluate((main) =>
    [...main.querySelectorAll("p, span, input, select, textarea, li")]
      .filter((element) => {
        if (!element.getClientRects().length) return false;
        const bounds = element.getBoundingClientRect();
        return bounds.right > innerWidth + 1 || bounds.left < -1;
      })
      .map((element) => element.tagName),
  );
  expect(clipped).toEqual([]);
}

async function screenshot(page: Page, name: string) {
  if (!process.env.POLISH_SCREENSHOTS) return;
  await page.evaluate(() => {
    const label = document.createElement("div");
    label.id = "fixture-label";
    label.textContent = "FRONTEND TEST FIXTURE · NOT LIVE DATA";
    label.style.cssText =
      "position:fixed;right:8px;bottom:88px;z-index:9999;background:#18181b;color:#fafafa;padding:6px;font:10px monospace;border:1px solid #52525b";
    document.body.appendChild(label);
  });
  await page.screenshot({
    path: path.resolve(
      "../docs/screenshots/trader-polish",
      `${name}-fixture.png`,
    ),
    fullPage: true,
    animations: "disabled",
  });
  await page.locator("#fixture-label").evaluate((element) => element.remove());
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "iphone", width: 390, height: 844 },
  { name: "iphone-landscape", width: 844, height: 390 },
]) {
  test(`${viewport.name}: scoped surfaces retain readable records and explicit sample states`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize(viewport);
    await installFixtures(page);
    for (const [route, title] of [
      ["/", "Dashboard"],
      ["/agent", "Agent"],
      ["/journal", "Journal"],
      ["/journal/statistics", "Journal statistics"],
    ]) {
      await page.goto(route);
      await expect(
        page.getByRole("heading", { level: 1, name: title, exact: true }),
      ).toBeVisible();
      await expect(page.getByLabel("Paper mode active").first()).toBeVisible();
      if (route === "/") {
        await expect(page.getByTestId("dashboard-expectancy")).toContainText(
          "+8.33",
        );
        await expect(
          page.getByTestId("dashboard-open-positions"),
        ).toContainText("BTCUSDT");
        await expect(page.getByTestId("dashboard-daily-status")).toContainText(
          "Overtrading warning",
        );
      } else if (route === "/agent") {
        await expect(
          page.getByRole("heading", { name: "What are you working through?" }),
        ).toBeVisible();
        await page
          .getByRole("button", { name: "Review the paper trade", exact: true })
          .click();
        await expect(page.getByTestId("agent-message")).toHaveCount(2);
        await expect(page.getByTestId("agent-attach-image")).toBeDisabled();
      } else if (route === "/journal") {
        await expect(page.getByTestId("journal-trades")).toContainText(
          "ETHUSDT",
        );
        await page.getByLabel("Search recent records").fill("BTC");
        await expect(page.getByTestId("journal-trades")).toContainText(
          "No matching trades",
        );
        await expect(page.getByTestId("journal-entries")).toContainText(
          "BTCUSDT",
        );
        await page.getByLabel("Search recent records").clear();
      } else {
        await expect(page.getByText("Overall (filtered)")).toBeVisible();
        await expect(
          page
            .getByText(
              "Only 3 closed trades; insufficient sample for reliable conclusions.",
            )
            .first(),
        ).toBeVisible();
        await page
          .getByText("More filters · regime, compliance, actor, and dates")
          .click();
        await expect(page.getByLabel("Market regime")).toBeVisible();
      }
      await expectFits(page);
      if (viewport.name !== "iphone-landscape")
        await screenshot(
          page,
          `${viewport.name}-${route === "/" ? "dashboard" : route.slice(1).replaceAll("/", "-")}`,
        );
    }
    expect(errors).toEqual([]);
  });
}

test("failed sources never become empty records or zero measurements", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installFixtures(page, "failed");
  await page.goto("/");
  await expect(page.getByTestId("dashboard-equity")).toContainText("—");
  await expect(page.getByTestId("dashboard-open-positions")).toContainText(
    "Open positions unavailable",
  );
  await page.goto("/journal");
  await expect(page.getByTestId("journal-trades")).toContainText(
    "Trades unavailable",
  );
  await expect(page.getByText("No canonical trades yet.")).toHaveCount(0);
  await screenshot(page, "iphone-journal-unavailable");
  await page.goto("/journal/statistics");
  await expect(page.getByText(/Closed paper trades unavailable/)).toBeVisible();
  await expect(
    page.getByText("No closed canonical journal trades in this list."),
  ).toHaveCount(0);
  await page.goto("/agent");
  await expect(page.getByTestId("agent-history-error")).toBeVisible();
  await expectFits(page);
});

test("empty sources keep unmeasured win rate and expectancy explicit", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installFixtures(page, "empty");
  await page.goto("/");
  await expect(page.getByTestId("dashboard-win-rate")).toContainText(
    "No closed trades yet",
  );
  await expect(page.getByTestId("dashboard-expectancy")).toContainText("—");
  await page.goto("/journal");
  await expect(page.getByTestId("journal-trades")).toContainText(
    "No canonical trades yet.",
  );
  await screenshot(page, "iphone-journal-empty");
  await expectFits(page);
  await page.goto("/journal/statistics");
  await expect(page.getByText("No recorded PnL samples").first()).toBeVisible();
  await expect(page.getByText("No closed journal trades", { exact: true })).toBeVisible();
});
