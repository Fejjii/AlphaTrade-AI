import { defineConfig, devices } from "@playwright/test";
import base from "./playwright.config";

/** Existing mobile specs in installed Chromium; does not claim Safari coverage. */
export default defineConfig({
  ...base,
  workers: 1,
  retries: 0,
  outputDir: "/tmp/alphatrade-mobile-chromium-results",
  projects: ["iPhone 15 Pro", "iPhone 15 Pro landscape"].map((device) => ({
    name: `chromium-${device}`,
    testMatch: ["**/webkit-iphone-audit.spec.ts", "**/notification-settings-v2.spec.ts"],
    use: {
      ...devices[device],
      browserName: "chromium" as const,
      launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ?? "/usr/bin/chromium" },
    },
  })),
});
