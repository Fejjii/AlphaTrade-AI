import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  AgentWorkspace,
  AGENT_TURN_TIMEOUT_MS,
} from "@/components/agent/AgentWorkspace";
import * as browserVoice from "@/lib/voice/browser-voice-provider";
import type { VoiceProvider } from "@/lib/voice/types";

let testParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => testParams,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "00000000-0000-0000-0000-000000000002" }, organization: { id: "00000000-0000-0000-0000-000000000001" } }),
}));
const apiMocks = vi.hoisted(() => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  getConversation: vi.fn(),
  agentTurn: vi.fn(),
  confirmProposal: vi.fn(),
  rejectProposal: vi.fn(),
  listPositions: vi.fn(),
  listStrategies: vi.fn(),
  getStrategy: vi.fn(),
  marketStatus: vi.fn(),
  previewFile: vi.fn(),
  importFile: vi.fn(),
  ingest: vi.fn(),
  killSwitchActive: false,
}));

vi.mock("@/lib/api", () => ({
  api: {
    conversations: {
      list: apiMocks.listConversations,
      listMessages: apiMocks.listMessages,
      get: apiMocks.getConversation,
    },
    chat: { message: vi.fn() },
    agent: {
      turn: apiMocks.agentTurn,
      confirmProposal: apiMocks.confirmProposal,
      rejectProposal: apiMocks.rejectProposal,
    },
    positions: { list: apiMocks.listPositions },
    strategies: { list: apiMocks.listStrategies, get: apiMocks.getStrategy },
    canonical: { getMarketStatus: apiMocks.marketStatus },
    knowledge: {
      previewFile: apiMocks.previewFile,
      importFile: apiMocks.importFile,
      ingest: apiMocks.ingest,
    },
  },
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ killSwitchActive: apiMocks.killSwitchActive }),
}));

describe("Agent workspace", () => {
  beforeEach(() => {
    sessionStorage.clear();
    apiMocks.getConversation.mockResolvedValue({ strategy_id: null });
    testParams = new URLSearchParams();
    apiMocks.listConversations.mockResolvedValue({
      items: [{ id: "c1", title: "BTC plan" }],
      total: 1,
      limit: 30,
      offset: 0,
    });
    apiMocks.listMessages.mockResolvedValue({
      items: [
        {
          id: "m1",
          role: "user",
          content: "Is this a pullback?",
          created_at: "2026-01-01",
        },
        {
          id: "m2",
          role: "assistant",
          content: "Paper only: wait for confirmation.",
          created_at: "2026-01-01",
        },
      ],
      total: 2,
      limit: 100,
      offset: 0,
    });
    apiMocks.listPositions.mockResolvedValue({
      items: [{ id: "p1", symbol: "BTCUSDT", direction: "long" }],
      total: 1,
      limit: 20,
      offset: 0,
    });
    apiMocks.listStrategies.mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    apiMocks.marketStatus.mockResolvedValue({
      availability: "fresh",
      symbol: "BTCUSDT",
    });
    apiMocks.agentTurn.mockResolvedValue({
      user_message_id: "m1", assistant_message_id: "m2",
      conversation_id: "c1",
      reply: "Noted.\n\nRecorded facts (not a confirmation):\nDraft only.",
      capability: "general_conversation",
      operation: "read",
      proposals: [],
      limitations: [],
      authority_mutated: false,
      execution_attempted: false,
      real_trading_enabled: false,
    });
    apiMocks.confirmProposal.mockResolvedValue({
      proposal_id: "p1",
      conversation_id: "c1",
      kind: "propose_journal_entry",
      artifact_kind: "journal_entry",
      status: "applied",
      summary: "Journal draft",
      content_hash: "a".repeat(64),
      applied: true,
      authority_mutated: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.restoreAllMocks();
    vi.useRealTimers();
    apiMocks.killSwitchActive = false;
  });

  function enableVoice(text: string) {
    const provider: VoiceProvider = {
      capabilities: { input: true, output: true },
      listen: vi.fn((callbacks) => {
        callbacks.onComplete(text);
        return { stop: vi.fn(), cancel: vi.fn() };
      }),
      speak: vi.fn(() => ({ stop: vi.fn(), cancel: vi.fn() })),
      dispose: vi.fn(),
    };
    vi.spyOn(browserVoice, "createBrowserVoiceProvider").mockReturnValue(
      provider,
    );
    return provider;
  }

  it("collapses evidence in existing assistant transcripts and preserves user text", async () => {
    const marker = "\n\nRecorded facts (not a confirmation):\n";
    apiMocks.listMessages.mockResolvedValue({
      items: [
        {
          id: "u",
          role: "user",
          created_at: "2026-01-01",
          content: `My quotation${marker}Keep this inline.`,
        },
        {
          id: "a",
          role: "assistant",
          created_at: "2026-01-01",
          content: `Conclusion: wait.\n\nStored evidence is stale; it cannot establish a current price.${marker}version=raw-id; hash=abc123`,
        },
      ],
    });
    render(<AgentWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    const summary = await screen.findByText("Stored evidence");
    const details = summary.closest("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(summary.tagName).toBe("SUMMARY");
    expect(details).toHaveTextContent("version=raw-id; hash=abc123");
    const messages = screen.getAllByTestId("agent-message");
    expect(messages[0].querySelector("details")).toBeNull();
    expect(messages[0]).toHaveTextContent("Keep this inline.");
    expect(screen.getByText(/Conclusion: wait/).closest("details")).toBeNull();
    expect(screen.getByText(/Stored evidence is stale/)).toBeVisible();
    fireEvent.click(summary);
    await waitFor(() => expect(details).toHaveAttribute("open"));
  });

  it("renders full stored evidence when a new transcript contains only an excerpt", async () => {
    apiMocks.listMessages.mockResolvedValue({
      items: [
        {
          id: "a",
          role: "assistant",
          created_at: "2026-01-01",
          content:
            "Conclusion: wait.\n\nRecorded facts (not a confirmation):\nEvidence excerpt.",
          payload: {
            interactive_agent: {
              recorded_evidence:
                "Nested approved. SFP approved. Full reference raw-id.",
            },
          },
        },
      ],
    });
    render(<AgentWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    const details = (await screen.findByText("Stored evidence")).closest(
      "details",
    )!;
    expect(details).toHaveTextContent(
      "Nested approved. SFP approved. Full reference raw-id.",
    );
    expect(details).not.toHaveTextContent("Evidence excerpt.");
    expect(details).not.toHaveAttribute("open");
  });

  it("presents bounded manual command choices as visible durable links", async () => {
    apiMocks.listMessages.mockResolvedValue({
      items: [
        {
          id: "choices",
          role: "assistant",
          created_at: "2026-10-08",
          content:
            "Multiple manual BloFin demo orders match. Select an exact command.",
          payload: {
            interactive_agent: {
              sources: [
                {
                  relation: "manual demo choice",
                  record_id: "original-command",
                  title: "12:56 UTC | 0.1 contracts | filled",
                },
                {
                  relation: "manual demo choice",
                  record_id: "blocked-command",
                  title: "13:02 UTC | 1 contracts | blocked",
                },
              ],
            },
          },
        },
      ],
    });
    render(<AgentWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    const choices = await screen.findByRole("list", {
      name: "Matching manual demo attempts",
    });
    expect(choices).toHaveTextContent("0.1 contracts | filled");
    expect(choices).toHaveTextContent("1 contracts | blocked");
    expect(
      screen.getByRole("link", { name: "12:56 UTC | 0.1 contracts | filled" }),
    ).toHaveAttribute("href", "/execution/manual-demo/original-command");
    expect(
      screen.getByRole("link", { name: "13:02 UTC | 1 contracts | blocked" }),
    ).toHaveAttribute("href", "/execution/manual-demo/blocked-command");
    expect(apiMocks.agentTurn).not.toHaveBeenCalled();
  });

  it("keeps full evidence available when the post-turn history request fails", async () => {
    apiMocks.listMessages.mockRejectedValue(new Error("History unavailable"));
    apiMocks.agentTurn.mockResolvedValue({
      user_message_id: "m1", assistant_message_id: "m2",
      conversation_id: "c1",
      reply:
        "Conclusion: wait.\n\nRecorded facts (not a confirmation):\nExcerpt.",
      recorded_evidence: "Full governed evidence beyond the reply budget.",
      full_reply: "Full additional explanation after the clean display ending.",
      connections: [{ title: "TradePlan", record_id: "plan-ref" }],
      capability: "general_conversation",
      operation: "read",
      proposals: [],
      limitations: [],
      authority_mutated: false,
      execution_attempted: false,
      real_trading_enabled: false,
    });
    render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Compare my strategies" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const details = (await screen.findByText("Stored evidence")).closest(
      "details",
    )!;
    expect(details).toHaveTextContent(
      "Full governed evidence beyond the reply budget.",
    );
    expect(details).toHaveTextContent(
      "Full additional explanation after the clean display ending.",
    );
    expect(details).toHaveTextContent("TradePlan: plan-ref");
    expect(details).not.toHaveAttribute("open");
  });

  it.each(["journal", "strategy", "knowledge", "Watcher", "trading", "risk"])(
    "uses one composer for voice about %s",
    async (topic) => {
      const text = `Review my ${topic}`;
      enableVoice(text);
      render(<AgentWorkspace />);
      fireEvent.click(screen.getByRole("button", { name: "History" }));
      fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
      await screen.findAllByTestId("agent-message");
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
      fireEvent.change(screen.getByLabelText("Voice transcript"), {
        target: { value: text + " carefully" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Use transcript" }));
      expect(apiMocks.agentTurn).not.toHaveBeenCalled();
      expect(screen.getByLabelText("Message")).toHaveValue(text + " carefully");
      fireEvent.click(screen.getByRole("button", { name: "Send" }));
      await waitFor(() =>
        expect(apiMocks.agentTurn).toHaveBeenCalledExactlyOnceWith(
          {
            message: text + " carefully",
            conversation_id: "c1",
            source_document_id: undefined,
          },
          { signal: expect.any(AbortSignal), headers: { "Idempotency-Key": expect.any(String) } },
        ),
      );
      expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
    },
  );

  it("retains a failed message in the unified composer and displays a completed reply when history fails", async () => {
    enableVoice("Review risk before trading");
    apiMocks.agentTurn.mockRejectedValueOnce(new Error("Turn unavailable"));
    apiMocks.listMessages.mockRejectedValue(new Error("History unavailable"));
    render(<AgentWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    fireEvent.click(screen.getByRole("button", { name: "Use transcript" }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Turn unavailable",
    );
    expect(screen.getByLabelText("Message")).toHaveValue(
      "Review risk before trading",
    );
    fireEvent.click(screen.getByRole("button", { name: "Recover original request" }));
    await screen.findAllByTestId("agent-message");
    expect(apiMocks.agentTurn).toHaveBeenCalledTimes(2);
    expect(apiMocks.agentTurn.mock.calls[1][0]).toEqual(apiMocks.agentTurn.mock.calls[0][0]);
    expect(apiMocks.agentTurn.mock.calls[1][1].headers).toEqual(apiMocks.agentTurn.mock.calls[0][1].headers);
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
  });

  it("recovers the original key and payload after a lost response and remount", async () => {
    apiMocks.agentTurn.mockRejectedValueOnce(new Error("Response lost"));
    const first = render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "My original intent" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText(/Response lost/);
    const original = apiMocks.agentTurn.mock.calls[0];
    first.unmount();
    render(<AgentWorkspace />);
    await screen.findByTestId("agent-turn-recovery");
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Edited text stays separate" } });
    fireEvent.click(screen.getByRole("button", { name: "Recover original request" }));
    await waitFor(() => expect(apiMocks.agentTurn).toHaveBeenCalledTimes(2));
    expect(apiMocks.agentTurn.mock.calls[1][0]).toEqual(original[0]);
    expect(apiMocks.agentTurn.mock.calls[1][1].headers).toEqual(original[1].headers);
    expect(original[0].conversation_id).toBeUndefined();
  });

  it("allows ordinary chat and voice while execution is globally paused", async () => {
    const provider = enableVoice("My rule: wait for confirmation");
    apiMocks.killSwitchActive = true;
    render(<AgentWorkspace />);
    expect(
      screen.getByRole("button", { name: "Start recording" }),
    ).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    fireEvent.click(screen.getByRole("button", { name: "Use transcript" }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(apiMocks.agentTurn).toHaveBeenCalledOnce());
    expect(provider.listen).toHaveBeenCalledOnce();
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
  });

  it("bounds a stalled Agent turn, retains the transcript, and does not retry automatically", async () => {
    enableVoice("Review my journal");
    apiMocks.agentTurn.mockImplementationOnce(
      (_body, { signal }: { signal: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    render(<AgentWorkspace />);
    await waitFor(() => expect(apiMocks.listConversations).toHaveBeenCalled());
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    fireEvent.click(screen.getByRole("button", { name: "Use transcript" }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await act(async () => vi.advanceTimersByTimeAsync(AGENT_TURN_TIMEOUT_MS));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "recover its saved result",
    );
    expect(screen.getByLabelText("Message")).toHaveValue("Review my journal");
    expect(apiMocks.agentTurn).toHaveBeenCalledTimes(1);
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
  });

  it("shows a completed turn even when its history reload stalls", async () => {
    enableVoice("Review risk before trading");
    apiMocks.listMessages.mockImplementationOnce(
      (_id, _params, { signal }: { signal: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    render(<AgentWorkspace />);
    await waitFor(() => expect(apiMocks.listConversations).toHaveBeenCalled());
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    fireEvent.click(screen.getByRole("button", { name: "Use transcript" }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await act(async () => vi.advanceTimersByTimeAsync(AGENT_TURN_TIMEOUT_MS));
    expect(screen.getByLabelText("Message")).toHaveValue("");
    expect(screen.getAllByTestId("agent-message")[1]).toHaveTextContent(
      "Stored evidence",
    );
    expect(apiMocks.agentTurn).toHaveBeenCalledTimes(1);
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
  });

  it("previews an attachment before sending and passes only its persisted document reference", async () => {
    apiMocks.previewFile.mockResolvedValue({
      title: "rules",
      extracted_text: "Risk remains governed.",
      warnings: [],
      preview_receipt: "preview-receipt",
    });
    apiMocks.importFile.mockResolvedValue({ document_id: "stored-doc" });
    render(<AgentWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "Attach document" }));
    const file = new File(["Risk remains governed."], "rules.txt", {
      type: "text/plain",
    });
    fireEvent.change(screen.getByLabelText("Attach document"), {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Use my rules" },
    });
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Preview attachment" }));
    expect(await screen.findByLabelText("Attachment preview")).toHaveValue(
      "Risk remains governed.",
    );
    expect(apiMocks.importFile).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(apiMocks.agentTurn).toHaveBeenCalledWith(
        {
          message: "Use my rules",
          conversation_id: undefined,
          source_document_id: "stored-doc",
        },
        { signal: expect.any(AbortSignal), headers: { "Idempotency-Key": expect.any(String) } },
      ),
    );
    expect(apiMocks.importFile).toHaveBeenCalledWith(
      file,
      "rules",
      "general_note",
      "preview-receipt",
    );
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
  });

  it("keeps the complete explanation and technical source references inside Stored evidence", async () => {
    apiMocks.listMessages.mockResolvedValue({
      items: [
        {
          id: "a",
          role: "assistant",
          created_at: "2026-01-01",
          content: "BTC short: entry 84,714.1. Missing risk narrative.",
          payload: {
            interactive_agent: {
              full_reply:
                "Complete additional explanation with 9c8c5c4f-3a8c-5301-bb63-b6b6a9bdc1b2.",
              recorded_evidence: "Canonical amounts and hash: abc123",
              sources: [{ title: "TradePlan", record_id: "plan-ref" }],
            },
          },
        },
      ],
    });
    render(<AgentWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    const details = (await screen.findByText("Stored evidence")).closest(
      "details",
    )!;
    expect(details).not.toHaveAttribute("open");
    expect(details).toHaveTextContent("Complete additional explanation");
    expect(details).toHaveTextContent("TradePlan: plan-ref");
    expect(details).toHaveTextContent("Canonical amounts and hash");
    expect(screen.getByText(/BTC short: entry/).closest("details")).toBeNull();
    expect(screen.getByText(/BTC short: entry/)).toBeVisible();
  });

  it("has collapsed history, no permanent capability panel or standalone trade context", async () => {
    render(<AgentWorkspace />);
    expect(
      screen.queryByRole("button", { name: "BTC plan" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("agent-capability-boundary"),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Timeframe")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Attach document" }));
    expect(screen.getByLabelText("Attach document")).toHaveAttribute(
      "type",
      "file",
    );
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    const messages = await screen.findAllByTestId("agent-message");
    expect(messages[0]).toHaveAttribute("data-role", "user");
    expect(messages[1]).toHaveAttribute("data-role", "assistant");
    expect(screen.getByRole("button", { name: "History" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("confirms a proposal only from the explicit button", async () => {
    apiMocks.agentTurn.mockResolvedValue({
      user_message_id: "m1", assistant_message_id: "m2",
      conversation_id: "c1",
      reply: "Drafted a journal proposal.",
      capability: "journal_capture",
      operation: "propose",
      proposals: [
        {
          proposal_id: "p1",
          conversation_id: "c1",
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
    });
    render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Journal this trade." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByTestId("agent-proposals")).toHaveTextContent(
      "proposed",
    );
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm proposal" }));
    await waitFor(() =>
      expect(apiMocks.confirmProposal).toHaveBeenCalledTimes(1),
    );
    expect(apiMocks.confirmProposal).toHaveBeenCalledWith("p1", {
      conversation_id: "c1",
      expected_content_hash: "a".repeat(64),
      statement: "I confirm",
    }, { signal: expect.any(AbortSignal) });
    await waitFor(() => expect(screen.getByTestId("agent-proposals")).toHaveTextContent("applied"));
  });

  it("clears the previous conversation while loading another and preserves failed message drafts", async () => {
    apiMocks.listConversations.mockResolvedValue({
      items: [
        { id: "c1", title: "BTC plan" },
        { id: "c2", title: "ETH review" },
      ],
    });
    render(<AgentWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    await screen.findAllByTestId("agent-message");
    apiMocks.listMessages.mockRejectedValue(new Error("History offline"));
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(screen.getByRole("button", { name: "ETH review" }));
    expect(screen.queryByText("Is this a pullback?")).not.toBeInTheDocument();
    expect(
      await screen.findByText(/Conversation unavailable: History offline/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("What are you working through?"),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
    apiMocks.agentTurn.mockRejectedValue(new Error("Agent offline"));
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Review my risk" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Agent offline");
    expect(screen.getByLabelText("Message")).toHaveValue("Review my risk");
  });
  it.each(["empty", "incomplete", "same IDs", "failed"])("renders acknowledgment immediately and retains it through %s history", async (mode) => {
    let finish!: (value: unknown) => void;
    let fail!: (error: Error) => void;
    apiMocks.listMessages.mockImplementationOnce(() => new Promise((resolve, reject) => { finish = resolve; fail = reject; }));
    render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Stable turn" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findAllByTestId("agent-message");
    expect(screen.getByLabelText("Message")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Next intentional turn" } });
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
    expect(screen.getAllByTestId("agent-message").map(m => m.dataset.messageId)).toEqual(["m1", "m2"]);
    expect(screen.getAllByTestId("agent-message")[1]).toHaveTextContent("Noted.");
    await act(async () => {
      if (mode === "failed") fail(new Error("Refresh offline"));
      else finish({ items: mode === "empty" ? [] : mode === "incomplete" ? [{ id: "m1", role: "user", content: "Stable turn", created_at: "2026-10-09" }] : [
        { id: "m1", role: "user", content: "Stable turn", created_at: "2026-10-09" },
        { id: "m2", role: "assistant", content: "Noted.", created_at: "2026-10-09" },
      ] });
    });
    expect(screen.getAllByTestId("agent-message")).toHaveLength(2);
    expect(screen.getAllByTestId("agent-message")[1]).toHaveTextContent("Stored evidence");
    expect(apiMocks.agentTurn).toHaveBeenCalledTimes(1);
  });

  it("ignores an acknowledged turn arriving after conversation navigation", async () => {
    let finish!: (value: unknown) => void;
    apiMocks.agentTurn.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    const { rerender } = render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Old context" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    testParams = new URLSearchParams("conversation=other");
    apiMocks.listMessages.mockResolvedValue({ items: [{ id: "other-message", role: "assistant", content: "Other conversation", created_at: "2026-10-09" }] });
    rerender(<AgentWorkspace />);
    await screen.findByText("Other conversation");
    await act(async () => finish({ conversation_id: "c1", user_message_id: "m1", assistant_message_id: "m2", reply: "Late private response", proposals: [] }));
    expect(screen.queryByText("Late private response")).not.toBeInTheDocument();
    expect(screen.queryByText("Old context")).not.toBeInTheDocument();
  });

  it("ignores history arriving out of order after switching conversation", async () => {
    let finish!: (value: unknown) => void;
    apiMocks.listMessages.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    testParams = new URLSearchParams("conversation=first");
    const { rerender } = render(<AgentWorkspace />);
    testParams = new URLSearchParams("conversation=second");
    apiMocks.listMessages.mockResolvedValue({ items: [{ id: "second-message", role: "assistant", content: "Second history", created_at: "2026-10-09" }] });
    rerender(<AgentWorkspace />);
    await screen.findByText("Second history");
    await act(async () => finish({ items: [{ id: "first-message", role: "assistant", content: "Late first history", created_at: "2026-10-09" }] }));
    expect(screen.queryByText("Late first history")).not.toBeInTheDocument();
  });

  it("authorizes strategy context before sending and performs no navigation mutation", async () => {
    testParams = new URLSearchParams("strategy_id=owned-strategy");
    apiMocks.getStrategy.mockResolvedValue({ id: "owned-strategy", name: "Owned plan" });
    render(<AgentWorkspace />);
    await screen.findByText("Strategy: Owned plan");
    expect(apiMocks.agentTurn).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Back to strategy" })).toHaveAttribute("href", "/strategy-lab/owned-strategy");
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Discuss changes" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(apiMocks.agentTurn).toHaveBeenCalledWith(expect.objectContaining({ strategy_id: "owned-strategy", message: "Discuss changes" }), expect.any(Object)));
  });

  it("blocks sending when strategy access fails", async () => {
    testParams = new URLSearchParams("strategy_id=unauthorized");
    apiMocks.getStrategy.mockRejectedValue(new Error("Not found"));
    render(<AgentWorkspace />);
    await screen.findByText("Strategy unavailable: Not found");
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Discuss changes" } });
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(apiMocks.agentTurn).not.toHaveBeenCalled();
  });

  it("aborts a turn on logout and discards its late acknowledgment", async () => {
    const { sessionCleared } = await import("@/lib/auth/session-events");
    let finish!: (value: unknown) => void;
    apiMocks.agentTurn.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Private pending turn" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const signal = apiMocks.agentTurn.mock.calls[0][1].signal;
    act(() => sessionCleared());
    expect(signal.aborted).toBe(true);
    await act(async () => finish({ conversation_id: "old", user_message_id: "u", assistant_message_id: "a", reply: "Late private acknowledgment" }));
    expect(screen.queryByText("Late private acknowledgment")).not.toBeInTheDocument();
    expect(screen.queryByText("Private pending turn")).not.toBeInTheDocument();
  });

  it("a pending proposal decision cannot alter a newly selected conversation", async () => {
    let finish!: (value: unknown) => void;
    apiMocks.agentTurn.mockResolvedValue({ conversation_id: "c1", user_message_id: "u", assistant_message_id: "a", reply: "Draft proposal",
      proposals: [{ proposal_id: "p1", conversation_id: "c1", summary: "Draft journal", status: "proposed", kind: "propose_journal_entry" }] });
    apiMocks.confirmProposal.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    const { rerender } = render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Draft" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    fireEvent.click(await screen.findByRole("button", { name: "Confirm proposal" }));
    testParams = new URLSearchParams("conversation=other");
    apiMocks.listMessages.mockResolvedValue({ items: [] });
    rerender(<AgentWorkspace />);
    await act(async () => finish({ proposal_id: "p1", conversation_id: "c1", status: "applied" }));
    expect(screen.queryByTestId("agent-proposals")).not.toBeInTheDocument();
  });

  it("cancels a pending turn on unmount and starts no history reconciliation for a late reply", async () => {
    let finish!: (value: unknown) => void;
    apiMocks.agentTurn.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    const { unmount } = render(<AgentWorkspace />);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Pending" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const signal = apiMocks.agentTurn.mock.calls[0][1].signal;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => finish({ conversation_id: "old", user_message_id: "u", assistant_message_id: "a", reply: "Late" }));
    expect(apiMocks.listMessages).not.toHaveBeenCalled();
  });

});
