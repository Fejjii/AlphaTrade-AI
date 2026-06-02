import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

const e2eBackendEnv = {
  PYTHONPATH: "src",
  RATE_LIMIT_USE_REDIS: "false",
  MARKET_DATA_CACHE_USE_REDIS: "false",
  PROVIDER_MODE: "mock",
  MARKET_DATA_PROVIDER: "mock",
  JOURNAL_RAG_SYNC_ENABLED: "true",
  EMAIL_AUTO_VERIFY_LOCAL: "true",
  ACCESS_TOKEN_DENYLIST_ENABLED: "false",
  JWT_SECRET: "e2e-test-secret-at-least-32-characters-long",
  DATABASE_URL: "sqlite+pysqlite:///./.e2e-alphatrade.db",
  LOG_JSON: "false",
  CORS_ORIGINS: "http://localhost:3000,http://127.0.0.1:3000",
};

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: "**/capture-screenshots.spec.ts",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "screenshots",
      testMatch: "**/capture-screenshots.spec.ts",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER
    ? undefined
    : [
        {
          command: "bash scripts/run_e2e_server.sh",
          cwd: "../backend",
          env: e2eBackendEnv,
          url: `${apiURL}/health`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
        {
          command: "npm run dev -- --port 3000 --hostname localhost",
          env: { NEXT_PUBLIC_API_URL: apiURL },
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      ],
});
