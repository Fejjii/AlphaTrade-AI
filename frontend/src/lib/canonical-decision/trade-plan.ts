import type {
  ApprovalRequest,
  CanonicalExecutionReceiptRead,
  CanonicalTradePlanRevision,
  PaperOrder,
  PaperValidationCandidateItem,
  Position,
  TradeProposal,
} from "@/lib/api/types";
import type {
  PaperExecutionStatus,
  PaperExecutionView,
  TradePlanLevel,
  TradePlanViewModel,
} from "@/lib/canonical-decision/types";

function amountValue(value: { value: string; unit: string } | string | null | undefined): string | null {
  if (!value) return null;
  if (typeof value === "string") return value;
  return value.value;
}

export function paperOrderSize(order: PaperOrder): string {
  return order.size ?? order.quantity ?? "—";
}

export function mapPaperExecutionStatus(status: string | null | undefined): PaperExecutionStatus {
  const normalized = (status ?? "").toLowerCase();
  if (!normalized) return "not_started";
  if (normalized.includes("block")) return "blocked";
  if (normalized === "pending" || normalized === "open" || normalized === "new") return "pending";
  if (normalized === "submitting" || normalized === "accepted") return "submitting";
  if (normalized === "filled" || normalized === "closed" || normalized === "complete") return "filled";
  if (normalized === "cancelled" || normalized === "canceled") return "cancelled";
  if (normalized === "rejected" || normalized === "failed") return "rejected";
  return "unknown";
}

export function tradePlanFromProposal(
  proposal: TradeProposal,
  revision?: CanonicalTradePlanRevision | null,
): TradePlanViewModel {
  const targets: TradePlanLevel[] = revision
    ? revision.risk_and_exits.targets.map((target) => ({
        label: `Target ${target.order}`,
        price: amountValue(target.price),
        fraction: target.quantity_fraction,
      }))
    : proposal.exit.take_profits.map((level, index) => ({
        label: `Target ${index + 1}`,
        price: level.price,
        fraction: String(level.size_fraction),
      }));

  return {
    authority: revision ? "canonical" : "compatibility_projection",
    proposalId: proposal.id,
    revisionId: revision?.revision_id ?? null,
    planId: revision?.plan_id ?? null,
    candidateId: revision?.candidate_id ?? null,
    symbol: proposal.symbol,
    direction: proposal.direction,
    timeframe: proposal.timeframe,
    strategyId: proposal.strategy_id,
    entry: revision ? amountValue(revision.limit_price) ?? proposal.entry_price : proposal.entry_price,
    stop: revision ? amountValue(revision.risk_and_exits.stop) : proposal.exit.stop_loss,
    targets,
    size: revision ? amountValue(revision.quantity) : proposal.position_size,
    leverage: revision ? revision.risk_and_exits.leverage : proposal.leverage,
    riskBudget: revision ? amountValue(revision.risk_and_exits.risk_budget) : proposal.planned_loss_amount ?? null,
    maximumLoss: revision
      ? amountValue(revision.risk_and_exits.maximum_loss)
      : proposal.planned_loss_amount ?? null,
    rationale: proposal.rationale,
    contentHash: revision?.content_hash ?? null,
    correlationId: revision?.correlation_id ?? null,
    strategyVersionId: revision?.strategy_version_id ?? null,
    setupDefinitionId: revision?.setup_definition_id ?? null,
    evidenceIds: revision?.evidence_ids ?? [],
    validFrom: revision?.valid_from ?? null,
    validUntil: revision?.valid_until ?? null,
    createdAt: revision?.created_at ?? proposal.created_at,
    riskAction: proposal.risk_result?.action ?? null,
    riskSummary: proposal.risk_result?.summary ?? null,
    approvalRequired: proposal.approval_required,
    lineage: [
      { label: "Proposal", value: proposal.id, href: `/decision/plans/${proposal.id}` },
      { label: "Strategy", value: proposal.strategy_id, href: "/decision/strategy" },
      ...(revision
        ? [
            { label: "Plan revision", value: revision.revision_id },
            { label: "Candidate", value: revision.candidate_id },
            { label: "Content hash", value: revision.content_hash.slice(0, 16) },
          ]
        : [{ label: "Plan source", value: "Legacy proposal (no TradePlanRevision bound)" }]),
    ],
  };
}

export function executionFromOrder(
  order: PaperOrder | null,
  proposal: TradeProposal | null,
  approval: ApprovalRequest | null,
  blockReason: string | null,
): PaperExecutionView {
  return {
    orderId: order?.id ?? null,
    receiptId: null,
    proposalId: order?.proposal_id ?? proposal?.id ?? null,
    approvalId: order?.approval_id ?? approval?.id ?? null,
    status: order ? mapPaperExecutionStatus(order.status) : blockReason ? "blocked" : "not_started",
    symbol: order?.symbol ?? proposal?.symbol ?? null,
    side: order?.side ?? null,
    size: order ? paperOrderSize(order) : proposal?.position_size ?? null,
    mode: "paper",
    liveExecutionAvailable: false,
    createdAt: order?.created_at ?? null,
    blockReason,
    authority: "compatibility_projection",
  };
}

export function executionFromReceipt(read: CanonicalExecutionReceiptRead): PaperExecutionView {
  const projectionState = read.projection?.state;
  const outcome = read.receipt.blocked_reason_code
    ? "blocked"
    : projectionState ?? read.receipt.outcome;
  return {
    orderId: null,
    receiptId: read.receipt.receipt_id,
    proposalId: null,
    approvalId: read.receipt.authorization_id ?? null,
    status: mapPaperExecutionStatus(outcome),
    symbol: null,
    side: null,
    size: null,
    mode: "paper",
    liveExecutionAvailable: false,
    createdAt: read.receipt.created_at,
    blockReason: read.receipt.blocked_reason_code ?? null,
    authority: "canonical",
  };
}

export function positionLinkedToProposal(
  position: Position,
  proposal: TradeProposal,
): boolean {
  return position.symbol === proposal.symbol && position.direction === proposal.direction;
}

export function candidateSetupLabel(candidate: PaperValidationCandidateItem): string {
  return candidate.condition ?? candidate.strategy_id ?? "Unspecified setup";
}
