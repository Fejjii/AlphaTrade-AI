import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProposalDetailPanel } from "@/components/ProposalDetailPanel";
import type { ApprovalRequest, TradeProposal } from "@/lib/api/types";

vi.mock("@/lib/api", () => ({
  api: {
    execution: {
      paperOrder: vi.fn(),
    },
  },
}));

const proposal: TradeProposal = {
  id: "proposal-1",
  organization_id: "org-1",
  user_id: "user-1",
  strategy_id: "htf_trend_pullback",
  symbol: "BTCUSDT",
  timeframe: "4h",
  direction: "long",
  entry_price: "60000",
  position_size: "0.01",
  leverage: "3",
  exit: {
    invalidation: "break",
    stop_loss: "58000",
    take_profits: [{ price: "62000", size_fraction: 1 }],
  },
  confidence: 0.7,
  risk_level: "medium",
  rationale: "Pullback setup",
  status: "pending_approval",
  approval_required: true,
  created_at: new Date().toISOString(),
};

const approval: ApprovalRequest = {
  id: "approval-1",
  proposal_id: "proposal-1",
  organization_id: "org-1",
  user_id: "user-1",
  status: "pending",
  risk_level: "medium",
  confidence: 0.7,
  created_at: new Date().toISOString(),
};

describe("ProposalDetailPanel", () => {
  afterEach(() => cleanup());

  it("renders linked approval and disabled paper button when pending", () => {
    render(<ProposalDetailPanel proposal={proposal} approval={approval} />);

    expect(screen.getByText(/linked approval/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create paper order/i })).toBeDisabled();
    expect(screen.getByText(/approval is still pending/i)).toBeInTheDocument();
  });

  it("enables paper button when approval is approved", () => {
    render(
      <ProposalDetailPanel
        proposal={{ ...proposal, status: "approved" }}
        approval={{ ...approval, status: "approved" }}
      />,
    );

    expect(screen.getByRole("button", { name: /create paper order/i })).toBeEnabled();
  });
});
