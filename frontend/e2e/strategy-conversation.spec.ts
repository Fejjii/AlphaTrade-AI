import { expect, test } from "@playwright/test";

import { getSharedE2EAccessToken, installSharedE2ESession } from "./helpers/shared-e2e-auth";

const API_URL = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

const SAMPLE_CARD = {
  strategy_name: "Conversation E2E Pullback",
  market_type: "crypto_perp",
  asset_universe: ["BTCUSDT"],
  timeframes: ["4h", "1h"],
  entry_conditions: ["Pullback to EMA cluster"],
  confirmation_conditions: ["RSI reset above 40"],
  invalidation: ["Close below swing low"],
  stop_loss: ["Below invalidation swing"],
  take_profit_plan: ["TP1 at prior high"],
  runner_plan: ["Trail after TP1"],
  position_sizing: ["Max 1% account risk"],
  add_rules: ["No adds until TP1"],
  no_trade_rules: ["Skip if funding extreme"],
  backtest_rules: ["Placeholder — not run"],
  success_criteria: ["Win rate > 45% in paper"],
  validation_status: "draft",
};

test.describe("Strategy Lab conversation", () => {
  test("panel persists a discussion across reload without mutating authority", async ({
    page,
    request,
  }) => {
    const token = await getSharedE2EAccessToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const created = await request.post(`${API_URL}/strategies`, {
      headers,
      data: {
        name: "Conversation E2E Pullback",
        setup_type: "htf_trend_pullback",
        card: SAMPLE_CARD,
      },
    });
    expect(created.ok(), `create strategy HTTP ${created.status()}`).toBeTruthy();
    const strategy = (await created.json()) as { id: string };
    const marker = `Durable conversation ${Date.now()}`;

    await installSharedE2ESession(page, request);
    await page.goto(`/strategy-lab/${strategy.id}`);
    await expect(page.getByTestId("strategy-conversation-panel")).toBeVisible();
    await expect(
      page.getByText(/Structured proposals stay drafts until you confirm/i),
    ).toBeVisible();

    await page.getByTestId("strategy-conversation-composer").fill(marker);
    await page.getByTestId("strategy-conversation-send").click();
    await expect(page.getByText(marker)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("strategy-conversation-message-user")).toBeVisible();

    await page.reload();
    await expect(page.getByTestId("strategy-conversation-panel")).toBeVisible();
    await expect(page.getByText(marker)).toBeVisible();

    const conversations = await request.get(`${API_URL}/conversations`, {
      headers,
      params: { strategy_id: strategy.id },
    });
    expect(conversations.ok()).toBeTruthy();
    const listed = (await conversations.json()) as { items: Array<{ id: string }>; total: number };
    expect(listed.total).toBeGreaterThanOrEqual(1);

    const messages = await request.get(`${API_URL}/conversations/${listed.items[0].id}/messages`, {
      headers,
    });
    expect(messages.ok()).toBeTruthy();
    const body = (await messages.json()) as { total: number };
    expect(body.total).toBeGreaterThanOrEqual(1);

    const versions = await request.get(`${API_URL}/strategies/${strategy.id}/versions`, {
      headers,
    });
    expect(versions.ok()).toBeTruthy();
    const versionPage = (await versions.json()) as { total: number };
    expect(versionPage.total).toBe(1);
  });
});
