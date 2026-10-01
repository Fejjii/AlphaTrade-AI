import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const destinations = [
  { label: "Dashboard", href: "/" },
  { label: "Agent", href: "/agent" },
  { label: "Journal", href: "/journal" },
  { label: "Strategies", href: "/strategies" },
  { label: "Knowledge", href: "/knowledge" },
  { label: "Settings", href: "/settings" },
];

async function installUnavailableSources(page: Page) {
  await page
    .context()
    .addCookies([{ name: "alphatrade_session", value: "1", url: "http://127.0.0.1:3000" }]);
  await page.addInitScript(() => {
    sessionStorage.setItem("alphatrade_access_token", "frontend-fixture-only");
  });
  await page.route("http://localhost:8000/**", async (route) => {
    // Only session and paper posture are fixture values. Workspace sources fail
    // explicitly, so navigation checks cannot manufacture trading or market state.
    const fixtures: Record<string, unknown> = {
      "/health": {
        status: "ok",
        execution_mode: "paper",
        real_trading_enabled: false,
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
    };
    const pathname = new URL(route.request().url()).pathname;
    expect(route.request().method()).toBe("GET");
    if (pathname in fixtures) await route.fulfill({ json: fixtures[pathname] });
    else
      await route.fulfill({
        status: 503,
        json: { detail: "Frontend fixture: source unavailable" },
      });
  });
}

async function screenshot(page: Page, name: string) {
  if (!process.env.NAVIGATION_SCREENSHOTS) return;
  await page.evaluate(() => {
    const label = document.createElement("div");
    label.id = "fixture-label";
    label.textContent = "FRONTEND TEST FIXTURE · SOURCES UNAVAILABLE";
    label.style.cssText =
      "position:fixed;right:8px;bottom:88px;z-index:9999;background:#18181b;color:#fafafa;padding:6px;font:10px monospace;border:1px solid #52525b";
    document.body.appendChild(label);
  });
  await page.screenshot({
    path: path.resolve("../docs/screenshots/primary-navigation-6", `${name}.png`),
    animations: "disabled",
  });
  await page.locator("#fixture-label").evaluate((element) => element.remove());
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "iphone", width: 390, height: 844 },
  { name: "narrow-phone", width: 320, height: 740 },
  { name: "iphone-landscape", width: 844, height: 390 },
]) {
  test(`${viewport.name}: all six destinations remain visible, selectable, and readable`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize(viewport);
    await installUnavailableSources(page);
    await page.goto("/agent");
    const desktop = viewport.width >= 1024;
    const nav = desktop
      ? page.getByRole("navigation", { name: "Primary destinations" })
      : page.getByTestId("mobile-bottom-navigation");
    await expect(nav).toBeVisible();
    await expect(nav.getByRole("link")).toHaveCount(6);
    await expect(nav.getByRole("link")).toHaveText(destinations.map((item) => item.label));
    await expect(nav.getByRole("link", { name: "Agent", exact: true })).toHaveAttribute(
      "data-primary-workspace",
      "true",
    );
    // Keep the development-only Next.js overlay from intercepting phone tabs.
    await page.addStyleTag({
      content: "nextjs-portal { display: none; }",
    });
    for (const destination of destinations) {
      const link = nav.getByRole("link", {
        name: destination.label,
        exact: true,
      });
      await expect(link).toHaveAttribute("href", destination.href);
      const bounds = await link.boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.width).toBeGreaterThanOrEqual(44);
      expect(bounds!.height).toBeGreaterThanOrEqual(44);
      await link.click();
      await expect(
        page.getByRole("heading", {
          name: destination.label,
          exact: true,
          level: 1,
        }),
      ).toBeVisible();
      await expect(link).toHaveAttribute("aria-current", "page");
      await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
      await expect(page).toHaveURL(
        new RegExp(`${destination.href === "/" ? "/" : destination.href}$`),
      );
      if (
        ["Agent", "Knowledge", "Settings"].includes(destination.label) &&
        ["desktop", "iphone"].includes(viewport.name)
      ) {
        await screenshot(page, `${viewport.name}-${destination.label.toLowerCase()}`);
      }
    }
    if (desktop) {
      await page.getByTestId("sidebar-collapse-toggle").click();
      await expect(page.getByTestId("desktop-sidebar")).toHaveAttribute("data-collapsed", "true");
      await expect(nav.getByRole("link")).toHaveCount(6);
      await nav.getByRole("link", { name: "Knowledge", exact: true }).click();
      await expect(
        page.getByRole("heading", { name: "Knowledge", exact: true, level: 1 }),
      ).toBeVisible();
    } else {
      const sizes = await nav.locator("a span").evaluateAll((labels) =>
        labels.map((label) => ({
          text: label.textContent,
          width: label.getBoundingClientRect().width,
          availableWidth: label.parentElement!.getBoundingClientRect().width
            - parseFloat(getComputedStyle(label.parentElement!).paddingLeft)
            - parseFloat(getComputedStyle(label.parentElement!).paddingRight),
          scrollWidth: label.scrollWidth,
          clientWidth: label.clientWidth,
        })),
      );
      for (const label of sizes) {
        expect(label.width, `${label.text} fits its tab`).toBeLessThanOrEqual(
          label.availableWidth,
        );
        expect(label.scrollWidth).toBeLessThanOrEqual(label.clientWidth + 1);
      }
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true);
    }
    expect(errors).toEqual([]);
  });
}

test("contextual access preserves Knowledge deep links and retained specialized routes", async ({
  page,
}) => {
  await installUnavailableSources(page);
  await page.goto("/knowledge?category=rules&source=risk_policy&document=doc-existing&q=discipline");
  const sections = page.getByRole("navigation", { name: "Knowledge categories" });
  await expect(sections.getByRole("link", { name: "Trading Rules", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await sections.getByRole("link", { name: "Playbook", exact: true }).click();
  await expect(page).toHaveURL(/category=playbook/);
  const url = new URL(page.url());
  expect(url.searchParams.get("q")).toBe("discipline");
  expect(url.searchParams.get("document")).toBe("doc-existing");
  await page.getByRole("link", { name: "Review lessons", exact: true }).click();
  await expect(page).toHaveURL(/\/lessons$/);
  await expect(
    page
      .getByRole("navigation", { name: "Primary destinations" })
      .getByRole("link", { name: "Knowledge", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await page.goto("/settings");
  const parameters = page.getByRole("navigation", {
    name: "Settings sections",
  });
  await parameters.getByRole("link", { name: "Markets", exact: true }).click();
  await expect(page).toHaveURL(/#markets$/);
  await expect(page.getByRole("region", { name: "Markets", exact: true })).toBeVisible();
  await parameters.getByRole("link", { name: "Notifications", exact: true }).click();
  await expect(page).toHaveURL(/#notifications$/);
  await expect(page.getByRole("region", { name: "Notifications", exact: true })).toBeVisible();
  await parameters.getByRole("link", { name: "Account and system", exact: true }).click();
  await expect(page).toHaveURL(/#account-system$/);
  await expect(page.getByTestId("settings-runtime-posture")).toBeVisible();
  await parameters.getByRole("link", { name: "Strategies", exact: true }).click();
  await expect(page).toHaveURL(/#strategies$/);
  await expect(page.getByRole("region", { name: "Strategies", exact: true })).toBeVisible();
  for (const retained of ["/risk", "/watcher", "/market", "/settings/advanced"]) {
    await page.goto(retained);
    expect(new URL(page.url()).pathname).toBe(retained);
    // Existing pages may show their error state before the header when reads fail.
    const main = page.locator("#main");
    await expect(main.getByRole("heading", { level: 1 }).or(main.getByRole("alert")).first()).toBeVisible();
    await expect(
      page.getByRole("navigation", { name: "Primary destinations" }).getByRole("link"),
    ).toHaveCount(6);
    await expect(page.getByRole("navigation", { name: "Primary destinations" }).getByRole("link", { name: "Settings", exact: true })).toHaveAttribute("aria-current", "page");
  }
});
