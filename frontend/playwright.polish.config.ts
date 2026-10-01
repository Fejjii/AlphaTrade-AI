import { defineConfig } from "@playwright/test";

/** Frontend-only contract fixtures; no backend server or external account needed. */
export default defineConfig({
  testDir: "./ui-tests",
  testMatch: "trader-polish.spec.ts",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  workers: 1,
  outputDir: "/tmp/alphatrade-polish-test-results",
  use: {
    baseURL: "http://127.0.0.1:3000",
    browserName: "chromium",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1",
    url: "http://127.0.0.1:3000/login",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
