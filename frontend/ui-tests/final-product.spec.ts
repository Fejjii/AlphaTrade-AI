import { expect, test, type Page } from "@playwright/test";

const workspaces = [
  { name: "Dashboard", href: "/", loading: "Loading dashboard" },
  { name: "Agent", href: "/agent", loading: "Loading open positions" },
  { name: "Journal", href: "/journal", loading: "Loading" },
  { name: "Strategies", href: "/strategies", loading: "Loading strategies" },
  { name: "Knowledge", href: "/knowledge", loading: "Loading Knowledge workspace" },
  { name: "Settings", href: "/settings", loading: "Loading" },
  { name: "Watcher", href: "/watcher", loading: "Loading" },
  { name: "Signals", href: "/tradingview-signals", loading: "Loading TradingView signals" },
];

async function fits(page: Page, workspace: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), workspace).toBe(true);
  const clipped = await page.locator("#main").evaluate((main) =>
    [...main.querySelectorAll("button, input, select, textarea")]
      .filter((element) => {
        const box = element.getBoundingClientRect();
        return box.width > 0 && (box.left < -1 || box.right > innerWidth + 1);
      }).map((element) => element.getAttribute("aria-label") ?? element.textContent),
  );
  expect(clipped, `${workspace}: controls fit`).toEqual([]);
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "phone", width: 390, height: 844 },
  { name: "phone-landscape", width: 844, height: 390 },
]) {
  for (const workspace of workspaces) {
    test(`${viewport.name}: ${workspace.name} loading, unavailable source and navigation`, async ({ page }) => {
      await page.setViewportSize(viewport);
      const errors: string[] = [];
      const forbidden: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.context().addCookies([{ name: "alphatrade_session", value: "1", url: "http://127.0.0.1:3000" }]);
      await page.addInitScript(() => sessionStorage.setItem("alphatrade_access_token", "acceptance-fixture-only"));
      let release!: () => void;
      const gate = new Promise<void>((resolve) => { release = resolve; });
      // Every remote request is fulfilled/aborted. No backend or speech service.
      await page.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === "http://127.0.0.1:3000") return route.continue();
        if (url.origin !== "http://localhost:8000" || request.method() !== "GET") {
          forbidden.push(`${request.method()} ${url.origin}${url.pathname}`);
          return route.abort();
        }
        const chrome: Record<string, unknown> = {
          "/health": { status: "ok", execution_mode: "paper", real_trading_enabled: false, exchange_mode: "paper_internal", must_verify_email: false },
          "/auth/me": { user: { id: "fixture-user", email: "fixture@example.com", email_verified: true }, organization: { id: "fixture-org", name: "Acceptance fixture" } },
          "/providers/status": { providers: [] },
          "/risk/kill-switch": { active: false, global_active: false, execution_blocked: false },
        };
        if (url.pathname in chrome) return route.fulfill({ json: chrome[url.pathname] });
        await gate;
        return route.fulfill({ status: 503, json: { detail: "Acceptance fixture: source unavailable" } });
      });
      try {
        await page.goto(workspace.href, { waitUntil: "domcontentloaded" });
        await page.addStyleTag({ content: "nextjs-portal { display: none; }" });
        await expect(page.locator("#main").getByText(new RegExp(workspace.loading), { exact: false }).first()).toBeVisible();
        await fits(page, `${workspace.name} loading`);
      } finally {
        release();
      }
      await expect(page.locator("#main").getByText(/unavailable|source unavailable/i).first()).toBeVisible();
      await expect(page.locator("#main").getByText(/Loading/).first()).not.toBeVisible();
      await fits(page, `${workspace.name} unavailable`);
      const nav = viewport.width >= 1024
        ? page.getByRole("navigation", { name: "Primary destinations" })
        : page.getByTestId("mobile-bottom-navigation");
      await expect(nav).toBeVisible();
      await nav.getByRole("link", { name: "Agent", exact: true }).click();
      await expect(page).toHaveURL(/\/agent$/);
      await expect(page.getByRole("heading", { name: "Agent", exact: true, level: 1 })).toBeVisible();
      expect(errors).toEqual([]);
      expect(forbidden).toEqual([]);
    });
  }
}
