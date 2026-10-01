import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentWorkspace } from "@/components/agent/AgentWorkspace";
import { missingAgentCapabilities } from "@/components/agent/agent-contracts";

const apiMocks = vi.hoisted(() => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  agentTurn: vi.fn(),
  confirmProposal: vi.fn(),
  rejectProposal: vi.fn(),
  listPositions: vi.fn(),
  listStrategies: vi.fn(),
  marketStatus: vi.fn(),
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
  },
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({ killSwitchActive: false }),
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
  });

  it("separates user and agent messages and keeps attachment controls unwired", async () => {
    render(<AgentWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    const messages = await screen.findAllByTestId("agent-message");
    expect(messages[0]).toHaveAttribute("data-role", "user");
    expect(messages[0]).toHaveTextContent("You");
    expect(messages[1]).toHaveAttribute("data-role", "assistant");
    expect(messages[1]).toHaveTextContent("Agent");
    expect(screen.getByTestId("agent-attach-image")).toBeDisabled();
    expect(screen.getByTestId("agent-voice")).toBeDisabled();
    expect(document.querySelector("input[type='file']")).toBeNull();
    expect(screen.getByTestId("agent-capability-boundary")).toHaveTextContent(
      "Image and screenshot attachment",
    );
    expect(
      screen.getByText(
        "Screenshot analysis is not available. No image is uploaded or interpreted.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Voice is not available. No audio is transcribed or played.",
      ),
    ).toBeInTheDocument();
    for (const missing of missingAgentCapabilities()) {
      expect(screen.getByText(missing.label)).toBeInTheDocument();
    }
  });

  it("sends text with trade context and does not invent an attachment payload", async () => {
    render(<AgentWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: /BTCUSDT/ }));
    fireEvent.change(screen.getByLabelText("Timeframe"), {
      target: { value: "1h" },
    });
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Review this long." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(apiMocks.agentTurn).toHaveBeenCalledTimes(1));
    expect(apiMocks.agentTurn).toHaveBeenCalledWith({
      message: "Review this long.",
      conversation_id: undefined,
      symbol: "BTCUSDT",
      timeframe: "1h",
      strategy_id: undefined,
    });
    expect(apiMocks.confirmProposal).not.toHaveBeenCalled();
    expect(apiMocks.rejectProposal).not.toHaveBeenCalled();
    expect(await screen.findByTestId("agent-market-context")).toHaveTextContent(
      "fresh",
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
    fireEvent.click(await screen.findByRole("button", { name: "BTC plan" }));
    await screen.findAllByTestId("agent-message");
    apiMocks.listMessages.mockRejectedValue(new Error("History offline"));
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
