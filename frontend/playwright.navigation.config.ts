import { defineConfig } from "@playwright/test";

import base from "./playwright.polish.config";

/** Navigation fixtures use existing API contracts without a backend or account. */
export default defineConfig({
  ...base,
  testMatch: "primary-navigation.spec.ts",
  outputDir: "/tmp/alphatrade-navigation-test-results",
});
