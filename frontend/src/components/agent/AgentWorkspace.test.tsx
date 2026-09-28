import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentWorkspace } from "@/components/agent/AgentWorkspace";
import { missingAgentCapabilities } from "@/components/agent/agent-contracts";

const apiMocks = vi.hoisted(() => ({
  listConversations: vi.fn(),
  listMessages: vi.fn(),
  chatMessage: vi.fn(),
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
    chat: { message: apiMocks.chatMessage },
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
        { id: "m1", role: "user", content: "Is this a pullback?", created_at: "2026-01-01" },
        { id: "m2", role: "assistant", content: "Paper only: wait for confirmation.", created_at: "2026-01-01" },
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
    apiMocks.listStrategies.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    apiMocks.marketStatus.mockResolvedValue({ availability: "fresh", symbol: "BTCUSDT" });
    apiMocks.chatMessage.mockResolvedValue({
      conversation_id: "c1",
      request_id: "r1",
      reply: "Noted.",
      citations: [],
      approval_required: false,
      approval_status: "none",
      tool_outputs: [],
      limitations: [],
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
      screen.getByText("Screenshot attachment is not available. The chat API accepts text only."),
    ).toBeInTheDocument();
    for (const missing of missingAgentCapabilities()) {
      expect(screen.getByText(missing.label)).toBeInTheDocument();
    }
  });

  it("sends text with trade context and does not invent an attachment payload", async () => {
    render(<AgentWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: /BTCUSDT/ }));
    fireEvent.change(screen.getByLabelText("Timeframe"), { target: { value: "1h" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Review this long." } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(apiMocks.chatMessage).toHaveBeenCalledTimes(1));
    expect(apiMocks.chatMessage).toHaveBeenCalledWith({
      message: "Review this long.",
      conversation_id: undefined,
      symbol: "BTCUSDT",
      timeframe: "1h",
      strategy_id: undefined,
    });
    expect(await screen.findByTestId("agent-market-context")).toHaveTextContent("fresh");
  });
});
