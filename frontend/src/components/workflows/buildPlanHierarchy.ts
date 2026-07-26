import type { PlanHierarchyModel } from "@/components/workflows/types";
import type { ApprovalRequest, TradeProposal } from "@/lib/api/types";

export type PlanHierarchyInput = {
  proposals?: TradeProposal[];
  approvals?: ApprovalRequest[];
};

function takeProfitLabel(proposal: TradeProposal): string | null {
  const levels = proposal.exit.take_profits ?? [];
  if (!levels.length) return null;
  return levels.map((level) => level.price).filter(Boolean).join(" / ") || null;
}

function paperExecutionState(proposal: TradeProposal, approval: ApprovalRequest | null): string {
  if (proposal.risk_result?.action === "block") {
    return "Paper execution blocked by risk engine";
  }
  if (approval?.status === "approved") {
    return "Approved for paper execution only";
  }
  if (approval?.status === "pending" || proposal.status === "pending_approval") {
    return "Awaiting human approval — paper only";
  }
  if (approval?.status === "rejected") {
    return "Rejected — no paper execution";
  }
  return "Draft / planning — no live orders";
}

/**
 * Pick the most relevant in-flight plan and expose the required hierarchy fields.
 */
export function buildPlanHierarchy(input: PlanHierarchyInput): PlanHierarchyModel | null {
  const proposals = input.proposals ?? [];
  const approvals = input.approvals ?? [];
  if (!proposals.length && !approvals.length) return null;

  const pendingApproval =
    approvals.find((item) => item.status === "pending" || item.status === "needs_more_analysis") ??
    null;
  const proposalFromApproval = pendingApproval
    ? proposals.find((item) => item.id === pendingApproval.proposal_id) ?? null
    : null;
  const pendingProposal =
    proposals.find((item) => item.status === "pending_approval") ?? proposals[0] ?? null;
  const proposal = proposalFromApproval ?? pendingProposal;
  if (!proposal) {
    return {
      proposalId: pendingApproval?.proposal_id ?? null,
      approvalId: pendingApproval?.id ?? null,
      symbol: null,
      direction: null,
      timeframe: null,
      thesis: pendingApproval?.approval_reason ?? "Approval pending — proposal details unavailable.",
      entry: null,
      invalidation: null,
      stopLoss: null,
      takeProfit: null,
      riskSummary: null,
      size: null,
      approvalState: pendingApproval?.status ?? "unknown",
      paperExecutionState: "Awaiting proposal context — paper only",
      riskBlocked: false,
      blockReason: null,
      proposalHref: pendingApproval ? `/proposals?id=${pendingApproval.proposal_id}` : "/proposals",
      approvalHref: pendingApproval ? `/approvals?id=${pendingApproval.id}` : "/approvals",
      confidence: pendingApproval?.confidence ?? null,
    };
  }

  const approval =
    approvals.find((item) => item.proposal_id === proposal.id) ?? pendingApproval ?? null;
  const riskBlocked = proposal.risk_result?.action === "block";
  const blockReason =
    proposal.risk_result?.summary ??
    proposal.risk_result?.triggered_rules?.[0]?.message ??
    null;

  return {
    proposalId: proposal.id,
    approvalId: approval?.id ?? null,
    symbol: proposal.symbol,
    direction: proposal.direction,
    timeframe: proposal.timeframe,
    thesis: proposal.rationale,
    entry: proposal.entry_price,
    invalidation: proposal.exit.invalidation,
    stopLoss: proposal.exit.stop_loss,
    takeProfit: takeProfitLabel(proposal),
    riskSummary: proposal.risk_result?.summary ?? `Risk level: ${proposal.risk_level}`,
    size: proposal.position_size,
    approvalState: approval?.status ?? proposal.status,
    paperExecutionState: paperExecutionState(proposal, approval),
    riskBlocked,
    blockReason: riskBlocked ? blockReason : null,
    proposalHref: `/proposals?id=${proposal.id}`,
    approvalHref: approval ? `/approvals?id=${approval.id}` : "/approvals",
    confidence: proposal.confidence,
  };
}
