/** Paper execution eligibility — mirrors backend execution policy. */

import type { ApprovalRequest, ApprovalStatus, TradeProposal } from "@/lib/api/types";

const BLOCKED_APPROVAL_STATUSES: ApprovalStatus[] = [
  "pending",
  "rejected",
  "modified",
  "needs_more_analysis",
  "paused",
  "cancelled",
  "closed",
];

export function canExecutePaperOrder(
  proposal: TradeProposal,
  approval: ApprovalRequest | null | undefined,
): { allowed: boolean; reason?: string } {
  if (proposal.loss_acceptance_required) {
    const status = proposal.loss_acceptance_status ?? "pending";
    if (status === "pending") {
      return { allowed: false, reason: "Loss acceptance required before paper execution." };
    }
    if (status === "rejected") {
      return { allowed: false, reason: "Planned loss was not accepted — reduce size or skip." };
    }
  }
  if (proposal.risk_result?.action === "block") {
    return { allowed: false, reason: "Blocked by risk engine." };
  }
  if (proposal.status === "rejected") {
    return { allowed: false, reason: "Proposal was rejected." };
  }
  if (proposal.approval_required && !approval) {
    return { allowed: false, reason: "Approval record required before paper execution." };
  }
  if (approval) {
    if (approval.proposal_id !== proposal.id) {
      return { allowed: false, reason: "Approval does not match proposal." };
    }
    if (BLOCKED_APPROVAL_STATUSES.includes(approval.status)) {
      if (approval.status === "pending") {
        return { allowed: false, reason: "Approval is still pending." };
      }
      return {
        allowed: false,
        reason: `Approval status is ${approval.status.replaceAll("_", " ")}; paper execution requires approved.`,
      };
    }
  }
  return { allowed: true };
}

export function paperSideForDirection(direction: string): "buy" | "sell" {
  return direction === "short" ? "sell" : "buy";
}

export function newIdempotencyKey(prefix = "paper"): string {
  return `${prefix}-${crypto.randomUUID()}`;
}
