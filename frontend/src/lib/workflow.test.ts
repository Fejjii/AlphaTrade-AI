import { describe, expect, it } from "vitest";

import type { ApprovalRequest, TradeProposal } from "@/lib/api/types";
import { canExecutePaperOrder } from "@/lib/workflow";

const baseProposal: TradeProposal = {
  id: "p1",
  organization_id: "o1",
  user_id: "u1",
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
  rationale: "test",
  status: "approved",
  approval_required: true,
  created_at: new Date().toISOString(),
};

const approvedApproval: ApprovalRequest = {
  id: "a1",
  proposal_id: "p1",
  organization_id: "o1",
  user_id: "u1",
  status: "approved",
  risk_level: "medium",
  confidence: 0.7,
  created_at: new Date().toISOString(),
};

describe("canExecutePaperOrder", () => {
  it("allows approved proposal with approved approval", () => {
    expect(canExecutePaperOrder(baseProposal, approvedApproval)).toEqual({ allowed: true });
  });

  it("blocks rejected approval", () => {
    expect(
      canExecutePaperOrder(baseProposal, { ...approvedApproval, status: "rejected" }).allowed,
    ).toBe(false);
  });

  it("blocks needs more analysis", () => {
    expect(
      canExecutePaperOrder(baseProposal, { ...approvedApproval, status: "needs_more_analysis" })
        .allowed,
    ).toBe(false);
  });

  it("blocks risk-blocked proposal", () => {
    expect(
      canExecutePaperOrder(
        {
          ...baseProposal,
          risk_result: {
            action: "block",
            severity: "high",
            triggered_rules: [],
            summary: "blocked",
          },
        },
        approvedApproval,
      ).allowed,
    ).toBe(false);
  });
});
