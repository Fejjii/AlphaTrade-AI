import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const timestamp = "2026-10-01T10:00:00Z";
const makeDocument = (
  id: string,
  title: string,
  source_type: string,
  source_uri: string | null = null,
) => ({
  id,
  title,
  source_type,
  source_uri,
  source_hash: "fixture-hash",
  version: 1,
  created_at: timestamp,
  updated_at: timestamp,
});
const documents = [
  makeDocument("rules-doc", "Risk before entry", "risk_policy"),
  makeDocument("playbook-doc", "Pullback playbook", "trading_playbook"),
  makeDocument(
    "lesson-doc",
    "Accepted lesson",
    "review_note",
    "lesson://lesson-1",
  ),
  makeDocument(
    "strategy-doc",
    "Strategy research",
    "strategy_template",
    "strategy://strategy-1/v1",
  ),
  makeDocument(
    "observation-doc",
    "Recorded market observation",
    "general_note",
    `https://example.com/${"source".repeat(50)}`,
  ),
  makeDocument(
    "journal-doc",
    "Journal observation",
    "trade_journal",
    "journal://entry-1",
  ),
];
const lesson = {
  id: "lesson-1",
  organization_id: "fixture-org",
  user_id: "fixture-user",
  source_type: "coaching",
  related_strategy_id: "strategy-1",
  related_journal_entry_id: "entry-1",
  lesson_text: "Wait for the confirmed close.",
  mistake_type: "early_entry",
  severity: "low",
  status: "accepted",
  created_at: timestamp,
};
const paginate = (items: unknown[]) => ({
  items,
  total: items.length,
  limit: 50,
  offset: 0,
});

async function fixture(
  page: Page,
  state = { mode: "populated" },
  gate?: Promise<void>,
) {
  await page
    .context()
    .addCookies([
      { name: "alphatrade_session", value: "1", url: "http://127.0.0.1:3000" },
    ]);
  await page.addInitScript(() =>
    sessionStorage.setItem("alphatrade_access_token", "frontend-fixture-only"),
  );
  const records = [...documents];
  await page.route("http://localhost:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const shell: Record<string, unknown> = {
      "/health": {
        status: "ok",
        execution_mode: "paper",
        real_trading_enabled: false,
        paper_only: true,
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
    if (url.pathname in shell)
      return route.fulfill({ json: shell[url.pathname] });
    if (url.pathname === "/knowledge/documents") {
      if (gate) await gate;
      if (state.mode === "failed")
        return route.fulfill({
          status: 503,
          json: { detail: "Fixture documents unavailable" },
        });
      const source = url.searchParams.get("source_type");
      const matched =
        state.mode === "empty"
          ? []
          : records.filter((doc) => !source || doc.source_type === source);
      return route.fulfill({ json: paginate(matched) });
    }
    if (url.pathname === "/knowledge/chunks")
      return route.fulfill({
        json: paginate([
          {
            id: "fixture-chunk",
            document_id: url.searchParams.get("document_id"),
            chunk_ordinal: 0,
            section_title: "Trading context",
            content: "Original stored trading context.",
            metadata: { source_type: "review_note" },
            created_at: timestamp,
          },
        ]),
      });
    if (url.pathname === "/lessons/candidates")
      return route.fulfill({ json: paginate([lesson]) });
    if (url.pathname === "/lessons/candidates/lesson-1")
      return route.fulfill({ json: lesson });
    if (url.pathname === "/knowledge/search")
      return route.fulfill({
        json: {
          query: request.postDataJSON().query,
          chunks: [
            {
              chunk_id: "fixture-chunk",
              document_id: "lesson-doc",
              title: "Memory result",
              source_type: "review_note",
              chunk_ordinal: 0,
              score: 0.9,
              content: lesson.lesson_text,
            },
          ],
          citations: [],
          degraded: false,
          fallback_used: false,
        },
      });
    if (url.pathname === "/knowledge/ingest") {
      const body = request.postDataJSON();
      records.push(makeDocument("new-note", body.title, body.source_type));
      return route.fulfill({
        json: {
          document_id: "new-note",
          chunk_count: 1,
          duplicate: false,
          version: 1,
          source_hash: "fixture-hash",
        },
      });
    }
    throw new Error(
      `Unexpected fixture API request: ${request.method()} ${url.pathname}`,
    );
  });
}

async function fits(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  expect(
    await page
      .locator('[data-testid="knowledge-hub-page"]')
      .evaluate((workspace) =>
        [
          ...workspace.querySelectorAll(
            "p, span, input, select, textarea, li, a, button",
          ),
        ]
          .filter((element) => {
            if (!element.getClientRects().length) return false;
            const bounds = element.getBoundingClientRect();
            return bounds.left < -1 || bounds.right > innerWidth + 1;
          })
          .map((element) => element.tagName),
      ),
  ).toEqual([]);
  expect(
    await page.locator("[data-nextjs-dialog], .vite-error-overlay").count(),
  ).toBe(0);
}

for (const [name, width, height] of [
  ["desktop", 1440, 1000],
  ["iphone", 390, 844],
  ["iphone-landscape", 844, 390],
] as const) {
  test(`Knowledge sources, search and note flow at ${name}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await fixture(page);
    await page.goto("/knowledge");
    await expect(
      page.getByTestId("knowledge-document-card-playbook-doc"),
    ).toBeVisible();
    await fits(page);
    const nav = page.getByRole("navigation", { name: "Knowledge categories" });
    await nav.getByRole("link", { name: "Strategy Research" }).click();
    await expect(
      page.getByTestId("knowledge-document-card-strategy-doc"),
    ).toBeVisible();
    await expect(
      page.getByTestId("knowledge-document-card-playbook-doc"),
    ).toHaveCount(0);
    await page.getByTestId("knowledge-expand-strategy-doc").click();
    await expect(
      page.getByText("Original stored trading context."),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: lesson.lesson_text }),
    ).toHaveAttribute("href", "/lessons?candidate=lesson-1");
    await expect(
      page.getByRole("link", { name: "Related journal entry", exact: true }),
    ).toHaveAttribute("href", "/journal?entry=entry-1");
    await fits(page);
    await nav.getByRole("link", { name: "Lessons", exact: true }).click();
    await expect(
      page.getByTestId("knowledge-document-card-lesson-doc"),
    ).toBeVisible();
    await page.getByLabel("Search query").fill("confirmed close");
    const searchRequest = page.waitForRequest((request) =>
      request.url().endsWith("/knowledge/search"),
    );
    await page.getByRole("button", { name: "Search", exact: true }).click();
    expect((await searchRequest).postDataJSON()).toMatchObject({
      query: "confirmed close",
      source_types: ["review_note", "mistakes_database"],
    });
    await page.getByRole("link", { name: "Memory result" }).click();
    await expect(
      page.getByText("Original stored trading context."),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Journal entry", exact: true }),
    ).toHaveAttribute("href", "/journal?entry=entry-1");
    await nav.getByRole("link", { name: "Market Observations" }).click();
    // Category links preserve the explicitly requested document, which remains visible separately.
    await expect(
      page.getByTestId("knowledge-document-card-observation-doc"),
    ).toBeVisible();
    const observation = page.getByTestId("knowledge-document-card-observation-doc");
    await observation.getByText("Provenance details").click();
    await expect(observation.locator("details")).toContainText(documents[4].source_uri!);
    await fits(page);
    await observation.getByText("Provenance details").click();
    await page.getByRole("button", { name: "Add note" }).click();
    await page
      .getByLabel("Category", { exact: true })
      .selectOption("general_note");
    await page
      .getByLabel("Title", { exact: true })
      .fill("My market observation");
    await page.getByLabel("Document text").fill("Wait for the range break.");
    await fits(page);
    if (width < 1024)
      expect(
        await page
          .getByLabel("Title", { exact: true })
          .evaluate((input) => parseFloat(getComputedStyle(input).fontSize)),
      ).toBeGreaterThanOrEqual(16);
    const ingest = page.waitForRequest((request) =>
      request.url().endsWith("/knowledge/ingest"),
    );
    await page.getByRole("button", { name: "Save note" }).click();
    expect((await ingest).postDataJSON()).toEqual({
      title: "My market observation",
      text: "Wait for the range break.",
      source_type: "general_note",
    });
    await expect(page.getByTestId("knowledge-ingest-success")).toBeVisible();
    await expect(
      page.getByTestId("knowledge-document-card-new-note"),
    ).toBeVisible();
    await fits(page);
    expect(errors).toEqual([]);
    if (process.env.KNOWLEDGE_SCREENSHOTS) {
      await page.getByRole("button", { name: "Close note" }).click();
      await page.evaluate(() => {
        const label = document.createElement("div");
        label.textContent = "FRONTEND TEST FIXTURE · NOT LIVE DATA";
        label.style.cssText =
          "position:fixed;top:0;left:0;right:0;z-index:99999;padding:6px;background:#4a2b00;color:#fff;font:12px system-ui;text-align:center";
        document.body.append(label);
      });
      await page.screenshot({
        path: path.resolve(
          `../docs/screenshots/knowledge-workspace/${name}-fixture.png`,
        ),
        fullPage: true,
      });
    }
  });
}

test("Knowledge loading, unavailable, retry and empty states on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let release!: () => void;
  const gate = new Promise<void>((done) => {
    release = done;
  });
  const state = { mode: "failed" };
  await fixture(page, state, gate);
  await page.goto("/knowledge");
  await expect(page.getByText("Loading Knowledge workspace…")).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Knowledge categories" }),
  ).toBeVisible();
  release();
  await expect(
    page.getByText("Knowledge unavailable: Fixture documents unavailable"),
  ).toBeVisible();
  await expect(page.getByTestId("empty-state")).toHaveCount(0);
  state.mode = "empty";
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText("No knowledge yet")).toBeVisible();
  await fits(page);
});
