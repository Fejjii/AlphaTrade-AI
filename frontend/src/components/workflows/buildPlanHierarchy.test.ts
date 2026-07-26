import { describe, expect, it } from "vitest";

import { buildPlanHierarchy } from "@/components/workflows/buildPlanHierarchy";
import type { ApprovalRequest, TradeProposal } from "@/lib/api/types";

const proposal: TradeProposal = {
  id: "prop-1",
  organization_id: "org",
  user_id: "user",
  signal_id: null,
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
  rationale: "HTF pullback into demand with clear invalidation.",
  status: "pending_approval",
  approval_required: true,
  risk_result: {
    action: "block",
    severity: "high",
    triggered_rules: [
      {
        rule_id: "daily_loss_lock",
        action: "block",
        severity: "high",
        message: "Daily loss lock is active.",
      },
    ],
    summary: "Blocked by daily loss lock.",
  },
  created_at: "2026-07-26T11:00:00.000Z",
};

const approval: ApprovalRequest = {
  id: "appr-1",
  proposal_id: "prop-1",
  organization_id: "org",
  user_id: "user",
  status: "pending",
  risk_level: "medium",
  confidence: 0.7,
  created_at: "2026-07-26T11:01:00.000Z",
};

describe("buildPlanHierarchy", () => {
  it("exposes evidence and approval hierarchy fields", () => {
    const plan = buildPlanHierarchy({ proposals: [proposal], approvals: [approval] });
    expect(plan).toMatchObject({
      symbol: "BTCUSDT",
      entry: "65000",
      invalidation: "64000",
      stopLoss: "64000",
      takeProfit: "67000",
      size: "0.1",
      approvalState: "pending",
      thesis: proposal.rationale,
      proposalHref: "/proposals?id=prop-1",
      approvalHref: "/approvals?id=appr-1",
    });
  });

  it("cannot override a risk BLOCK", () => {
    const plan = buildPlanHierarchy({ proposals: [proposal], approvals: [approval] });
    expect(plan?.riskBlocked).toBe(true);
    expect(plan?.blockReason).toContain("daily loss lock");
    expect(plan?.paperExecutionState).toMatch(/blocked by risk engine/i);
    expect(plan?.paperExecutionState).toMatch(/runtime paper availability is separate/i);
  });
});

