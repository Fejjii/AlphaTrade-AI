import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StrategyConversationPanel } from "./StrategyConversationPanel";

const {
  listMock,
  listMessagesMock,
  listProposalsMock,
  confirmMock,
  rejectMock,
  chatMock,
  compileMock,
  approveMock,
} = vi.hoisted(() => ({
  listMock: vi.fn(),
  listMessagesMock: vi.fn(),
  listProposalsMock: vi.fn(),
  confirmMock: vi.fn(),
  rejectMock: vi.fn(),
  chatMock: vi.fn(),
  compileMock: vi.fn(),
  approveMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    conversations: {
      list: (...args: unknown[]) => listMock(...args),
      listMessages: (...args: unknown[]) => listMessagesMock(...args),
      listProposals: (...args: unknown[]) => listProposalsMock(...args),
      confirmProposal: (...args: unknown[]) => confirmMock(...args),
      rejectProposal: (...args: unknown[]) => rejectMock(...args),
    },
    chat: {
      message: (...args: unknown[]) => chatMock(...args),
    },
    strategies: {
      compileVersion: (...args: unknown[]) => compileMock(...args),
      approveVersion: (...args: unknown[]) => approveMock(...args),
    },
  },
}));

const draftProposal = {
  id: "prop-1",
  conversation_id: "conv-1",
  organization_id: "org",
  user_id: "user",
  status: "draft" as const,
  proposed_structured_rules: { entry_rules: [{ trigger_type: "ema_pullback" }] },
  proposed_pattern_spec: null,
  proposed_card: null,
  validation: { valid: true, errors: [], warnings: [] },
  limitations: ["This is a structured preview only."],
  challenge_notes: ["Consider an explicit no-trade filter."],
  content_hash: "ab".repeat(32),
  parent_version_id: "parent-1",
  target_strategy_id: "strat-1",
  created_at: "2026-09-20T10:00:00.000Z",
  updated_at: "2026-09-20T10:00:00.000Z",
  is_preview: true,
  mutates_strategy_authority: false,
};

describe("StrategyConversationPanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    listMock.mockResolvedValue({
      items: [{ id: "conv-1", organization_id: "org", user_id: "user", status: "active" }],
      total: 1,
      limit: 1,
      offset: 0,
    });
    listMessagesMock.mockResolvedValue({
      items: [
        {
          id: "m1",
          conversation_id: "conv-1",
          organization_id: "org",
          user_id: "user",
          role: "user",
          content: "Convert this HTF pullback idea into structured rules",
          created_at: "2026-09-20T10:00:00.000Z",
        },
        {
          id: "m2",
          conversation_id: "conv-1",
          organization_id: "org",
          user_id: "user",
          role: "assistant",
          content: "Draft structured rules generated. This remains a preview.",
          created_at: "2026-09-20T10:00:01.000Z",
        },
      ],
      total: 2,
      limit: 100,
      offset: 0,
    });
    listProposalsMock.mockResolvedValue({
      items: [draftProposal],
      total: 1,
      limit: 10,
      offset: 0,
    });
    confirmMock.mockResolvedValue({
      ...draftProposal,
      status: "confirmed",
      is_preview: false,
      mutates_strategy_authority: true,
      resulting_version_id: "ver-2",
    });
    rejectMock.mockResolvedValue({ ...draftProposal, status: "rejected", is_preview: false });
    compileMock.mockResolvedValue({ status: "executable", compiled: { id: "c1" }, failures: [] });
    approveMock.mockResolvedValue({ id: "life-1", new_state: "approved" });
  });

  it("loads the durable thread and keeps proposals as drafts until confirm", async () => {
    render(<StrategyConversationPanel strategyId="strat-1" />);
    expect(await screen.findByTestId("strategy-conversation-panel")).toBeInTheDocument();
    expect(screen.getByTestId("strategy-conversation-thread")).toHaveTextContent("HTF pullback");
    const proposal = screen.getByTestId("strategy-conversation-proposal");
    expect(proposal).toHaveAttribute("data-proposal-status", "draft");
    expect(proposal).toHaveTextContent(/preview only/i);
    expect(screen.getByTestId("strategy-conversation-confirm")).toBeInTheDocument();
  });

  it("sends chat with the bound strategy id", async () => {
    chatMock.mockResolvedValue({
      conversation_id: "conv-1",
      request_id: "r1",
      reply: "Context loaded",
      approval_required: false,
      approval_status: "not_required",
      citations: [],
      tool_outputs: [],
      limitations: [],
    });
    render(<StrategyConversationPanel strategyId="strat-1" />);
    await screen.findByTestId("strategy-conversation-composer");
    fireEvent.change(screen.getByTestId("strategy-conversation-composer"), {
      target: { value: "Challenge this idea against my journal" },
    });
    fireEvent.click(screen.getByTestId("strategy-conversation-send"));
    await waitFor(() => {
      expect(chatMock).toHaveBeenCalledWith({
        message: "Challenge this idea against my journal",
        conversation_id: "conv-1",
        strategy_id: "strat-1",
      });
    });
  });

  it("confirms a draft with an explicit I confirm token", async () => {
    render(<StrategyConversationPanel strategyId="strat-1" />);
    await screen.findByTestId("strategy-conversation-confirm");
    fireEvent.click(screen.getByTestId("strategy-conversation-confirm"));
    await waitFor(() => {
      expect(confirmMock).toHaveBeenCalledWith("conv-1", "prop-1", {
        confirm: "I confirm",
        expected_content_hash: "ab".repeat(32),
        expected_parent_version_id: "parent-1",
        expected_target_strategy_id: "strat-1",
      });
    });
  });

  it("rejects a draft without writing a version", async () => {
    render(<StrategyConversationPanel strategyId="strat-1" />);
    await screen.findByTestId("strategy-conversation-reject");
    fireEvent.click(screen.getByTestId("strategy-conversation-reject"));
    await waitFor(() => {
      expect(rejectMock).toHaveBeenCalledWith("conv-1", "prop-1", { confirm: "I reject" });
    });
  });

  it("compiles then approves only after an explicit confirmed draft", async () => {
    const confirmed = {
      ...draftProposal,
      status: "confirmed" as const,
      is_preview: false,
      mutates_strategy_authority: true,
      resulting_version_id: "ver-2",
    };
    confirmMock.mockImplementation(async () => {
      listProposalsMock.mockResolvedValue({
        items: [confirmed],
        total: 1,
        limit: 10,
        offset: 0,
      });
      return confirmed;
    });
    render(<StrategyConversationPanel strategyId="strat-1" />);
    await screen.findByTestId("strategy-conversation-confirm");
    fireEvent.click(screen.getByTestId("strategy-conversation-confirm"));
    await screen.findByTestId("strategy-conversation-compile");
    expect(screen.queryByTestId("strategy-conversation-confirm")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("strategy-conversation-compile"));
    await waitFor(() => {
      expect(compileMock).toHaveBeenCalledWith("strat-1", "ver-2");
    });
    await screen.findByTestId("strategy-conversation-compile-status");
    fireEvent.click(screen.getByTestId("strategy-conversation-approve"));
    await waitFor(() => {
      expect(approveMock).toHaveBeenCalledWith("strat-1", "ver-2", { confirm: "I confirm" });
    });
  });
});
