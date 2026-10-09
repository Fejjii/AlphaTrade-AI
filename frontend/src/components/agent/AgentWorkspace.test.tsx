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

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

const apiMocks = vi.hoisted(() => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  agentTurn: vi.fn(),
  confirmProposal: vi.fn(),
  rejectProposal: vi.fn(),
  listPositions: vi.fn(),
  listStrategies: vi.fn(),
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
    },
    chat: { message: vi.fn() },
    agent: {
      turn: apiMocks.agentTurn,
      confirmProposal: apiMocks.confirmProposal,
      rejectProposal: apiMocks.rejectProposal,
    },
    positions: { list: apiMocks.listPositions },
    strategies: { list: apiMocks.listStrategies },
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
          { signal: expect.any(AbortSignal) },
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
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findAllByTestId("agent-message");
    expect(apiMocks.agentTurn).toHaveBeenCalledTimes(2);
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
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
      "check conversation history before resending",
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
        { signal: expect.any(AbortSignal) },
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
    });
    expect(await screen.findByTestId("agent-proposals")).toHaveTextContent(
      "applied",
    );
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
});
