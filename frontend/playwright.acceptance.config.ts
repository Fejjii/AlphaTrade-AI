import { defineConfig } from "@playwright/test";
import polish from "./playwright.polish.config";

/** Local speech/API fixtures only. Each spec includes desktop and phone widths. */
export default defineConfig({
  ...polish,
  testMatch: [
    "voice-agent.spec.ts",
    "trader-polish.spec.ts",
    "primary-navigation.spec.ts",
    "knowledge-workspace.spec.ts",
    "final-product.spec.ts",
  ],
  outputDir: "/tmp/alphatrade-final-product-results",
  use: { ...polish.use, trace: "retain-on-failure", screenshot: "only-on-failure" },
});
