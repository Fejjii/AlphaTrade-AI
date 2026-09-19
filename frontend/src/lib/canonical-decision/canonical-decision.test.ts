import { describe, expect, it } from "vitest";

import { missingBindings } from "@/lib/canonical-decision/bindings";
import { composeDecisionCases, deriveProposalStage } from "@/lib/canonical-decision/compose";
import { projectActionEligibility } from "@/lib/canonical-decision/eligibility";
import { buildDecisionSteps } from "@/lib/canonical-decision/steps";
import { mapPaperExecutionStatus, tradePlanFromProposal } from "@/lib/canonical-decision/trade-plan";
import type { ApprovalRequest, PaperValidationCandidateItem, TradeProposal } from "@/lib/api/types";

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
  confidence: 0.72,
  risk_level: "medium",
  rationale: "Reclaim with defined invalidation.",
  status: "pending_approval",
  approval_required: true,
  created_at: "2026-09-19T12:00:00.000Z",
};

const approval: ApprovalRequest = {
  id: "appr-1",
  proposal_id: "prop-1",
  organization_id: "org",
  user_id: "user",
  status: "pending",
  risk_level: "medium",
  confidence: 0.72,
  created_at: "2026-09-19T12:01:00.000Z",
};

const candidate: PaperValidationCandidateItem = {
  candidate_id: "cand-1",
  draft_id: "draft-1",
  source_alert_id: "alert-1",
  symbol: "ETHUSDT",
  timeframe: "4h",
  condition: "liquidity_sweep",
  direction: "short",
  confidence: 0.8,
  thesis: "Sweep then displace.",
  entry_criteria: "Reclaim after sweep",
  invalidation_criteria: "Above sweep high",
  checklist_snapshot: {
    trend_checked: true,
    support_resistance_checked: true,
    volume_checked: false,
    risk_reward_checked: true,
    invalidation_checked: true,
    higher_timeframe_checked: false,
    news_or_funding_checked: false,
  },
  risk_mode: "moderate",
  candidate_status: "queued",
  created_at: "2026-09-19T11:00:00.000Z",
};

describe("canonical decision steps", () => {
  it("marks later paper stages blocked when the kill switch is on", () => {
    const steps = buildDecisionSteps({
      current: "eligibility",
      eligibilityBlocked: true,
      killSwitchActive: true,
    });
    expect(steps.find((step) => step.key === "eligibility")?.status).toBe("blocked");
    expect(steps.find((step) => step.key === "paper_execution")?.status).toBe("blocked");
    expect(steps.find((step) => step.key === "market_assessment")?.status).toBe("complete");
  });
});

describe("action eligibility projection", () => {
  it("keeps liveExecutable false and blocks on kill switch", () => {
    const view = projectActionEligibility({
      killSwitchActive: true,
      executionMode: "paper",
      realTradingEnabled: false,
    });
    expect(view.liveExecutable).toBe(false);
    expect(view.paperActionable).toBe(false);
    expect(view.state).toBe("blocked");
    expect(view.reasonCodes).toContain("blocked_kill_switch");
    expect(view.authority).toBe("compatibility_projection");
  });

  it("blocks real-trading configuration even if paper mode is claimed", () => {
    const view = projectActionEligibility({
      killSwitchActive: false,
      executionMode: "paper",
      realTradingEnabled: true,
    });
    expect(view.reasonCodes).toContain("blocked_configuration");
    expect(view.liveExecutable).toBe(false);
  });

  it("requires human approval before paper execution", () => {
    const view = projectActionEligibility({
      killSwitchActive: false,
      executionMode: "paper",
      realTradingEnabled: false,
      proposal,
      approval,
    });
    expect(view.reasonCodes).toContain("blocked_human_approval_required");
    expect(view.humanApprovalSatisfied).toBe(false);
  });
});

describe("composeDecisionCases", () => {
  it("keeps paper-validation candidates separate from proposals", () => {
    const snapshot = composeDecisionCases({
      candidates: [candidate],
      proposals: [proposal],
      approvals: [approval],
      orders: [],
      journals: [],
      lessons: [],
      killSwitchActive: false,
      executionMode: "paper",
      realTradingEnabled: false,
    });
    expect(snapshot.cases).toHaveLength(2);
    expect(snapshot.cases.some((item) => item.kind === "compatibility_candidate")).toBe(true);
    expect(snapshot.cases.some((item) => item.kind === "legacy_proposal")).toBe(true);
    expect(snapshot.missingBindings).toContain("canonical-candidates");
    expect(snapshot.missingBindings).toContain("action-eligibility");
  });

  it("advances a proposal to approval then paper execution", () => {
    expect(
      deriveProposalStage({
        proposal,
        approval,
        order: undefined,
        journal: undefined,
        lesson: undefined,
      }),
    ).toBe("approval");
    expect(
      deriveProposalStage({
        proposal: { ...proposal, status: "approved" },
        approval: { ...approval, status: "approved" },
        order: {
          id: "ord-1",
          symbol: "BTCUSDT",
          side: "buy",
          status: "filled",
          proposal_id: "prop-1",
          created_at: "2026-09-19T12:05:00.000Z",
        },
        journal: undefined,
        lesson: undefined,
      }),
    ).toBe("paper_execution");
  });
});

describe("trade plan mapping", () => {
  it("maps legacy proposal fields without inventing a revision hash", () => {
    const plan = tradePlanFromProposal(proposal);
    expect(plan.authority).toBe("compatibility_projection");
    expect(plan.entry).toBe("65000");
    expect(plan.stop).toBe("64000");
    expect(plan.targets[0]?.price).toBe("67000");
    expect(plan.contentHash).toBeNull();
    expect(plan.approvalRequired).toBe(true);
  });

  it("maps paper order statuses without a live state", () => {
    expect(mapPaperExecutionStatus("filled")).toBe("filled");
    expect(mapPaperExecutionStatus("pending")).toBe("pending");
  });
});

describe("backend bindings", () => {
  it("documents missing canonical HTTP authority", () => {
    const missing = missingBindings().map((item) => item.id);
    expect(missing).toEqual(
      expect.arrayContaining(["canonical-candidates", "action-eligibility", "execution-receipts"]),
    );
  });
});
