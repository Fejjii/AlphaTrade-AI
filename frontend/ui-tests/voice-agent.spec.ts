import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

type SpeechHarness = {
  start(): void;
  result(text: string, final: boolean): void;
  end(): void;
  error(code: string): void;
  aborts: number;
  speechCancels: number;
  spoken: string[];
};

declare global {
  interface Window {
    __voiceTest: SpeechHarness;
  }
}

async function installSpeech(page: Page, supported = true) {
  await page.addInitScript((enabled) => {
    const instances: Recognition[] = [];
    const harness: SpeechHarness = {
      start: () => instances[instances.length - 1].onstart?.(),
      result: (text, final) =>
        instances[instances.length - 1].onresult?.({
          results: [{ isFinal: final, 0: { transcript: text } }],
        }),
      end: () => instances[instances.length - 1].onend?.(),
      error: (code) =>
        instances[instances.length - 1].onerror?.({ error: code }),
      aborts: 0,
      speechCancels: 0,
      spoken: [],
    };
    class Recognition {
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onresult:
        | ((event: {
            results: { isFinal: boolean; 0: { transcript: string } }[];
          }) => void)
        | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      constructor() {
        instances.push(this);
      }
      start() {}
      stop() {}
      abort() {
        harness.aborts++;
      }
    }
    class Utterance {
      onstart: (() => void) | null = null;
      constructor(public text: string) {}
    }
    Object.defineProperty(window, "SpeechRecognition", {
      configurable: true,
      value: enabled ? Recognition : undefined,
    });
    Object.defineProperty(window, "webkitSpeechRecognition", {
      configurable: true,
      value: undefined,
    });
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      configurable: true,
      value: enabled ? Utterance : undefined,
    });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: enabled
        ? {
            speak: (utterance: Utterance) => {
              harness.spoken.push(utterance.text);
              utterance.onstart?.();
            },
            cancel: () => {
              harness.speechCancels++;
            },
          }
        : undefined,
    });
    window.__voiceTest = harness;
  }, supported);
}

async function installApi(
  page: Page,
  options: { failedTurn?: boolean; killSwitch?: boolean } = {},
) {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (["http://127.0.0.1:3000", "http://localhost:8000"].includes(url.origin)) {
      return route.continue();
    }
    await route.abort();
    throw new Error(`Voice acceptance forbids remote requests: ${url.origin}${url.pathname}`);
  });
  const posts: { path: string; body: unknown }[] = [];
  const messages = [
    {
      id: "old-user",
      role: "user",
      content: "Review my paper trade",
      created_at: "2026-10-01T09:00:00Z",
    },
    {
      id: "old-agent",
      role: "assistant",
      content: "Keep the recorded invalidation explicit.",
      created_at: "2026-10-01T09:00:00Z",
    },
  ];
  await page
    .context()
    .addCookies([
      { name: "alphatrade_session", value: "1", url: "http://127.0.0.1:3000" },
    ]);
  await page.addInitScript(() =>
    sessionStorage.setItem(
      "alphatrade_access_token",
      "voice-test-fixture-only",
    ),
  );
  await page.route("http://localhost:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const paginated = (items: unknown[]) => ({
      items,
      total: items.length,
      limit: 100,
      offset: 0,
    });
    if (request.method() === "POST") {
      posts.push({ path: url.pathname, body: request.postDataJSON() });
      expect(url.pathname).toBe("/agent/turns");
      if (options.failedTurn) {
        await route.fulfill({
          status: 503,
          json: { detail: "Agent temporarily unavailable" },
        });
        return;
      }
      const body = request.postDataJSON() as { message: string };
      const reply =
        "Review your recorded risk. A journal proposal requires explicit confirmation.";
      messages.push(
        {
          id: `user-${posts.length}`,
          role: "user",
          content: body.message,
          created_at: "2026-10-01T09:01:00Z",
        },
        {
          id: `agent-${posts.length}`,
          role: "assistant",
          content: reply,
          created_at: "2026-10-01T09:01:00Z",
        },
      );
      await route.fulfill({
        json: {
          conversation_id: "voice-c1",
          reply,
          capability: "journal_capture",
          operation: "propose",
          proposals: [
            {
              proposal_id: "journal-p1",
              conversation_id: "voice-c1",
              kind: "propose_journal_entry",
              artifact_kind: "journal_entry",
              status: "proposed",
              summary: "Journal draft",
              content_hash: "a".repeat(64),
              applied: false,
              authority_mutated: false,
            },
          ],
          limitations: [],
          authority_mutated: false,
          execution_attempted: false,
          real_trading_enabled: false,
        },
      });
      return;
    }
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
          id: "voice-user",
          email: "voice-fixture@example.com",
          email_verified: true,
        },
        organization: { id: "voice-org", name: "Voice test fixture" },
      },
      "/providers/status": { providers: [] },
      "/risk/kill-switch": {
        active: Boolean(options.killSwitch),
        global_active: false,
        execution_blocked: Boolean(options.killSwitch),
      },
      "/positions": paginated([]),
      "/strategies": paginated([
        { id: "strategy-1", name: "Fixture strategy" },
      ]),
      "/conversations": paginated([
        { id: "voice-c1", title: "Voice review" },
        { id: "voice-c2", title: "Another conversation" },
      ]),
      "/conversations/voice-c1/messages": paginated(messages),
      "/conversations/voice-c2/messages": paginated([]),
      "/canonical/market-status": {
        availability: "unavailable",
        symbol: "BTCUSDT",
      },
    };
    expect(
      url.pathname in fixtures,
      `Unexpected API request: ${url.pathname}`,
    ).toBe(true);
    await route.fulfill({ json: fixtures[url.pathname] });
  });
  return posts;
}

async function fits(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  const controls = page.getByRole("region", { name: "Voice controls" });
  const clipped = await controls.evaluate((element) =>
    [...element.querySelectorAll("button, p")]
      .filter((child) => {
        const box = child.getBoundingClientRect();
        return box.right > innerWidth + 1 || box.left < -1;
      })
      .map((child) => child.textContent),
  );
  expect(clipped).toEqual([]);
  for (const button of await controls.getByRole("button").all()) {
    expect((await button.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  }
}

async function screenshot(page: Page, name: string) {
  if (!process.env.VOICE_SCREENSHOTS) return;
  await page.evaluate(() => {
    const label = document.createElement("div");
    label.id = "voice-fixture-label";
    label.textContent = "FRONTEND + SPEECH TEST FIXTURE · NOT LIVE DATA";
    label.style.cssText =
      "position:fixed;right:8px;bottom:88px;z-index:9999;background:#18181b;color:#fafafa;padding:6px;font:10px monospace;border:1px solid #52525b";
    document.body.appendChild(label);
  });
  await page.screenshot({
    path: path.resolve("../docs/screenshots/voice-agent", `${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
  await page
    .locator("#voice-fixture-label")
    .evaluate((element) => element.remove());
}

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "phone", width: 390, height: 844 },
  { name: "phone-landscape", width: 844, height: 390 },
]) {
  test(`${viewport.name}: voice uses the existing conversation, keeps text, and interrupts speech`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize(viewport);
    await installSpeech(page);
    const posts = await installApi(page);
    await page.goto("/agent");
    await page
      .getByRole("button", { name: "Voice review", exact: true })
      .click();
    await expect(page.getByTestId("agent-message")).toHaveCount(2);
    await page.getByLabel("Symbol", { exact: true }).fill("BTCUSDT");
    await page.getByLabel("Timeframe", { exact: true }).fill("4h");
    await page
      .getByLabel("Strategy", { exact: true })
      .selectOption("strategy-1");
    await page
      .getByRole("textbox", { name: "Message", exact: true })
      .fill("Keep this text draft");
    await page.getByRole("button", { name: "Start recording" }).click();
    await expect(page.getByTestId("agent-voice-status")).toContainText(
      "permission",
    );
    await page.evaluate(() => {
      window.__voiceTest.start();
      window.__voiceTest.result(
        "Review my journal strategy knowledge Watcher trading and risk",
        false,
      );
    });
    await expect(page.getByTestId("agent-voice-status")).toContainText(
      "Recording",
    );
    await expect(
      page.getByRole("button", { name: "Send transcript" }),
    ).toBeDisabled();
    await fits(page);
    await screenshot(page, `${viewport.name}-recording`);
    await page.getByRole("button", { name: "Stop recording" }).click();
    await expect(page.getByTestId("agent-voice-status")).toContainText(
      "Transcribing",
    );
    await page.evaluate(() => {
      window.__voiceTest.result(
        "Review my journal strategy knowledge Watcher trading and risk",
        true,
      );
      window.__voiceTest.end();
    });
    await expect(page.getByTestId("agent-voice-status")).toContainText(
      "review before sending",
    );
    expect(posts).toEqual([]);
    await page.getByRole("button", { name: "Send transcript" }).click();
    await expect(page.getByTestId("agent-voice-status")).toContainText(
      "Transcript sent",
    );
    expect(posts).toEqual([
      {
        path: "/agent/turns",
        body: {
          message:
            "Review my journal strategy knowledge Watcher trading and risk",
          conversation_id: "voice-c1",
          symbol: "BTCUSDT",
          timeframe: "4h",
          strategy_id: "strategy-1",
        },
      },
    ]);
    await expect(
      page.getByRole("textbox", { name: "Message", exact: true }),
    ).toHaveValue("Keep this text draft");
    await expect(page.getByTestId("agent-message").last()).toContainText(
      "Review your recorded risk",
    );
    await expect(
      page.getByRole("button", { name: "Confirm proposal" }),
    ).toBeVisible();
    expect(await page.evaluate(() => window.__voiceTest.spoken)).toEqual([]);
    await page.getByRole("button", { name: "Read Agent reply" }).click();
    await expect(page.getByTestId("agent-speech-status")).toHaveText(
      "Speaking",
    );
    await screenshot(page, `${viewport.name}-speaking`);
    await page.getByRole("button", { name: "Stop speech" }).click();
    await expect(page.getByTestId("agent-speech-status")).toHaveText(
      "Speech off",
    );
    await page.getByRole("button", { name: "Read Agent reply" }).click();
    await page.getByRole("button", { name: "Start recording" }).click();
    await expect(page.getByTestId("agent-speech-status")).toHaveText(
      "Speech off",
    );
    await page.evaluate(() => {
      window.__voiceTest.start();
      window.__voiceTest.result("Do not send this", true);
    });
    await page.getByRole("button", { name: "Clear voice" }).click();
    await page.evaluate(() => window.__voiceTest.end());
    await expect(page.getByTestId("agent-voice-transcript")).toHaveCount(0);
    await expect(page.getByTestId("agent-voice-status")).toHaveText(
      "Microphone off",
    );
    await page.getByRole("button", { name: "Read Agent reply" }).click();
    await page
      .getByRole("button", { name: "Another conversation", exact: true })
      .click();
    await expect(page.getByTestId("agent-speech-status")).toHaveText(
      "Speech off",
    );
    expect(posts).toHaveLength(1);
    expect(errors).toEqual([]);
    await fits(page);
  });
}

test("permission failure leaves text usable", async ({ page }) => {
  await installSpeech(page);
  const posts = await installApi(page);
  await page.goto("/agent");
  await page.getByRole("button", { name: "Start recording" }).click();
  await page.evaluate(() => window.__voiceTest.error("not-allowed"));
  await expect(
    page.getByRole("region", { name: "Voice controls" }).getByRole("alert"),
  ).toContainText("permission was denied");
  await expect(
    page.getByRole("button", { name: "Start recording" }),
  ).toBeEnabled();
  expect(posts).toEqual([]);
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Review risk in text");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("agent-message").last()).toContainText(
    "Review your recorded risk",
  );
  expect(posts[0]).toEqual({
    path: "/agent/turns",
    body: { message: "Review risk in text" },
  });
});

for (const cancel of ["conversation", "page-hide"] as const) {
  test(`${cancel} cancels recording and playback and ignores late transcripts`, async ({ page }) => {
    await installSpeech(page);
    const posts = await installApi(page);
    await page.goto("/agent");
    await page.getByRole("button", { name: "Voice review", exact: true }).click();
    await expect(page.getByTestId("agent-message")).toHaveCount(2);
    const draft = page.getByRole("textbox", { name: "Message", exact: true });
    await draft.fill("Preserve my typed draft");
    await page.getByRole("button", { name: "Start recording" }).click();
    await page.evaluate(() => { window.__voiceTest.start(); window.__voiceTest.result("Never send this late result", false); });
    const aborts = await page.evaluate(() => window.__voiceTest.aborts);
    if (cancel === "conversation") {
      await page.getByRole("button", { name: "Another conversation", exact: true }).click();
    } else {
      await page.evaluate(() => {
        Object.defineProperty(document, "hidden", { configurable: true, value: true });
        document.dispatchEvent(new Event("visibilitychange"));
      });
    }
    await expect(page.getByTestId("agent-voice-status")).toHaveText("Microphone off");
    expect(await page.evaluate(() => window.__voiceTest.aborts)).toBeGreaterThan(aborts);
    await page.evaluate(() => { window.__voiceTest.result("Late transcript", true); window.__voiceTest.end(); });
    if (cancel === "conversation") {
      await expect(page.getByTestId("agent-voice-transcript")).toHaveCount(0);
    } else {
      await expect(page.getByTestId("agent-voice-transcript")).toContainText("Never send this late result");
      await expect(page.getByTestId("agent-voice-transcript")).not.toContainText("Late transcript");
      await expect(page.getByRole("button", { name: "Send transcript" })).toBeDisabled();
    }
    expect(posts).toEqual([]);
    if (cancel === "page-hide") {
      await expect(draft).toHaveValue("Preserve my typed draft");
      await page.evaluate(() => {
        Object.defineProperty(document, "hidden", { configurable: true, value: false });
        document.dispatchEvent(new Event("visibilitychange"));
      });
      await page.getByRole("button", { name: "Read Agent reply" }).click();
      await expect(page.getByTestId("agent-speech-status")).toHaveText("Speaking");
      const cancels = await page.evaluate(() => window.__voiceTest.speechCancels);
      await page.evaluate(() => {
        Object.defineProperty(document, "hidden", { configurable: true, value: true });
        document.dispatchEvent(new Event("visibilitychange"));
      });
      await expect(page.getByTestId("agent-speech-status")).toHaveText("Speech off");
      expect(await page.evaluate(() => window.__voiceTest.speechCancels)).toBeGreaterThan(cancels);
    }
  });
}

test("unsupported input and output keep the text composer usable", async ({
  page,
}) => {
  await installSpeech(page, false);
  const posts = await installApi(page);
  await page.goto("/agent");
  await expect(page.getByTestId("agent-voice")).toBeDisabled();
  await expect(
    page.getByText("Voice input is unavailable in this browser", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Read Agent reply" }),
  ).toBeDisabled();
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Review risk in text");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("agent-message").last()).toContainText(
    "Review your recorded risk",
  );
  expect(posts[0]).toEqual({
    path: "/agent/turns",
    body: { message: "Review risk in text" },
  });
});

test("failed turns retain the voice transcript; kill switch prevents recording", async ({
  page,
}) => {
  await installSpeech(page);
  const posts = await installApi(page, { failedTurn: true });
  await page.goto("/agent");
  await page.getByRole("button", { name: "Start recording" }).click();
  await page.evaluate(() => {
    window.__voiceTest.start();
    window.__voiceTest.result("Review my journal", true);
    window.__voiceTest.end();
  });
  await page.getByRole("button", { name: "Send transcript" }).click();
  await expect(
    page.getByTestId("agent-workspace").getByRole("alert"),
  ).toContainText("Agent temporarily unavailable");
  await expect(page.getByTestId("agent-voice-transcript")).toContainText(
    "Review my journal",
  );
  await expect(
    page.getByRole("button", { name: "Send transcript" }),
  ).toBeEnabled();
  expect(posts).toHaveLength(1);
  await page.unroute("http://localhost:8000/**");
  await installApi(page, { killSwitch: true });
  await page.reload();
  await expect(
    page.getByText("Kill switch is active. New messages are paused."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start recording" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Send transcript" }),
  ).toBeDisabled();
});
