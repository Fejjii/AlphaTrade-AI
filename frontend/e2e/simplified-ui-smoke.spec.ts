/**
 * Browser smoke for the six trader destinations and retained routes.
 * Screenshots are written for the release-candidate review.
 */
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { installSharedE2ESession, paperModeActive } from "./helpers/shared-e2e-auth";

const SHOTS = process.env.SIMPLIFIED_UI_SHOTS ?? "/opt/cursor/artifacts/screenshots";

const DESTINATIONS = [
  { route: "/", heading: "Dashboard", file: "dashboard" },
  { route: "/agent", heading: "Agent", file: "agent" },
  { route: "/journal", heading: "Journal", file: "journal" },
  { route: "/strategies", heading: "Strategies", file: "strategies" },
  { route: "/knowledge", heading: "Knowledge", file: "knowledge" },
  { route: "/settings", heading: "Settings", file: "settings" },
] as const;

const RETAINED = ["/strategy-lab", "/lessons", "/settings/advanced"] as const;

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(overflow).toBe(false);
}

test.describe("Simplified trader UI", () => {
  test("desktop and mobile widths keep the six destinations and retained routes", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    // Keep the supported Voice V1 state deterministic across browser builds.
    await page.addInitScript(() => {
      Object.defineProperty(window, "SpeechRecognition", {
        configurable: true,
        value: class {},
      });
    });
    await installSharedE2ESession(page, request);

    for (const viewport of [
      { width: 1280, height: 900, label: "desktop" },
      { width: 390, height: 844, label: "mobile" },
    ] as const) {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      for (const destination of DESTINATIONS) {
        await page.goto(destination.route);
        await expect(
          page.getByRole("heading", { level: 1, name: destination.heading }),
        ).toBeVisible();
        await expect(paperModeActive(page)).toBeVisible();
        await expect(page.getByRole("button", { name: /place real order/i })).toHaveCount(0);
        await expect(page.getByRole("button", { name: /execute live/i })).toHaveCount(0);
        await expectNoHorizontalOverflow(page);
        await page.screenshot({
          path: path.join(SHOTS, `${viewport.label}-${destination.file}.png`),
          fullPage: true,
          animations: "disabled",
        });
      }

      if (viewport.label === "mobile") {
        const nav = page.getByTestId("mobile-bottom-navigation");
        await expect(nav).toBeVisible();
        await expect(page.getByTestId("desktop-sidebar")).toBeHidden();
        // The Next.js dev overlay sits on the bottom tab bar and intercepts
        // pointer events. The product nav is still the link under it.
        await page.evaluate(() => {
          const portal = document.querySelector("nextjs-portal");
          if (portal instanceof HTMLElement) portal.style.pointerEvents = "none";
        });
        for (const name of [
          "Dashboard",
          "Agent",
          "Journal",
          "Strategies",
          "Knowledge",
          "Settings",
        ]) {
          await nav.getByRole("link", { name }).click();
          await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
        }
      } else {
        const nav = page.getByRole("navigation", {
          name: "Primary destinations",
        });
        await expect(nav).toBeVisible();
        await expect(page.getByTestId("mobile-bottom-navigation")).toBeHidden();
        for (const name of [
          "Agent",
          "Journal",
          "Strategies",
          "Knowledge",
          "Settings",
          "Dashboard",
        ]) {
          await nav.getByRole("link", { name }).click();
          await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
        }
      }
    }

    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/agent");
    await expect(page.getByTestId("agent-workspace")).toBeVisible();
    await expect(page.getByTestId("agent-attach-image")).toBeDisabled();
    await expect(page.getByTestId("agent-voice")).toBeVisible();
    await expect(page.getByTestId("agent-voice")).toBeEnabled();
    await expect(page.getByText("Screenshot analysis is not available.")).toBeVisible();
    await expect(page.getByText("Voice is not available.")).toHaveCount(0);
    await expect(page.locator('input[type="file"]')).toHaveCount(0);

    for (const route of RETAINED) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(paperModeActive(page)).toBeVisible();
      await expectNoHorizontalOverflow(page);
    }
  });
});
