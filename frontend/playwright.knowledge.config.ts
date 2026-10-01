import { defineConfig } from "@playwright/test";
import polish from "./playwright.polish.config";

/** Frontend-only Knowledge contract fixtures; no backend or external account. */
export default defineConfig({
  ...polish,
  testMatch: "knowledge-workspace.spec.ts",
  outputDir: "/tmp/alphatrade-knowledge-test-results",
  webServer: {
    ...polish.webServer,
    command:
      "NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev -- --hostname 127.0.0.1",
    url: "http://127.0.0.1:3000/login",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
