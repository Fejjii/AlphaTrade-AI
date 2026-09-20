import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PaperApprovalPanel } from "./PaperApprovalPanel";
import type { ApprovalRequest, TradeProposal } from "@/lib/api/types";

const executePaperPlan = vi.fn();
const paperOrder = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    execution: {
      executePaperPlan: (...args: unknown[]) => executePaperPlan(...args),
      paperOrder: (...args: unknown[]) => paperOrder(...args),
    },
  },
}));

const proposal: TradeProposal = {
  id: "prop-1",
  organization_id: "org",
  user_id: "user",
  strategy_id: "htf_trend_pullback",
  symbol: "BTCUSDT",
  timeframe: "1h",
  direction: "long",
  entry_price: "65000",
  position_size: "0.1",
  leverage: "1",
  exit: {
    invalidation: "64000",
    stop_loss: "64000",
    take_profits: [{ price: "67000", size_fraction: 1 }],
  },
  confidence: 0.7,
  risk_level: "medium",
  rationale: "Defined invalidation.",
  status: "approved",
  approval_required: true,
  created_at: "2026-09-19T12:00:00.000Z",
};

const approval: ApprovalRequest = {
  id: "appr-1",
  proposal_id: "prop-1",
  organization_id: "org",
  user_id: "user",
  status: "approved",
  risk_level: "medium",
  confidence: 0.7,
  created_at: "2026-09-19T12:01:00.000Z",
};

const canonicalApproval: ApprovalRequest = {
  ...approval,
  proposal_id: "canonical-root-1",
  plan_revision_id: "rev-1",
  authorization: {
    authorization_id: "auth-1",
    approval_request_id: "appr-1",
    organization_id: "org",
    user_id: "user",
    account_id: "acct-1",
    revision_id: "rev-1",
    plan_id: "plan-1",
    plan_content_hash: "ab".repeat(32),
    state: "AVAILABLE",
    expires_at: "2026-09-19T13:00:00.000Z",
  },
};

describe("PaperApprovalPanel", () => {
  afterEach(() => {
    cleanup();
    executePaperPlan.mockReset();
    paperOrder.mockReset();
  });

  it("uses paper-plan execution and never renders the legacy paper order button", () => {
    render(<PaperApprovalPanel approval={approval} proposal={proposal} />);
    expect(screen.getByTestId("canonical-paper-plan-button")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create paper order/i })).not.toBeInTheDocument();
    expect(paperOrder).not.toHaveBeenCalled();
  });

  it("shows paper-plan execute when the canonical workflow omits the compatibility proposal", () => {
    render(<PaperApprovalPanel approval={canonicalApproval} proposal={null} />);
    expect(screen.getByTestId("canonical-paper-plan-button")).toBeInTheDocument();
    expect(screen.getByTestId("execute-paper-plan-button")).toBeEnabled();
    expect(screen.queryByRole("button", { name: /create paper order/i })).not.toBeInTheDocument();
    expect(paperOrder).not.toHaveBeenCalled();
  });
});
