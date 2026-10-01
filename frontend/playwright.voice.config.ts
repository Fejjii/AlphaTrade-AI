import { defineConfig } from "@playwright/test";
import polish from "./playwright.polish.config";

/** Frontend contract fixtures with deterministic speech events, no live services. */
export default defineConfig({
  ...polish,
  testMatch: "voice-agent.spec.ts",
  outputDir: "/tmp/alphatrade-voice-test-results",
});
