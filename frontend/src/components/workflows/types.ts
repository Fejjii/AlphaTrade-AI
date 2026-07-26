import type { FreshnessState } from "@/components/ui/freshness-pill";

/** Attention queue section keys for the Dashboard daily loop. */
export type AttentionSectionId =
  | "safety"
  | "pending_decisions"
  | "new_signals"
  | "validation_work"
  | "positions_risk"
  | "lessons";

export type AttentionPriority = 1 | 2 | 3 | 4 | 5 | 6;

export type AttentionItemTone = "default" | "warning" | "danger" | "info" | "success";

export type AttentionItemModel = {
  id: string;
  section: AttentionSectionId;
  priority: AttentionPriority;
  title: string;
  summary: string;
  href: string;
  actionLabel: string;
  tone?: AttentionItemTone;
  meta?: string;
  count?: number;
};

export type SignalSourceKind =
  | "tradingview"
  | "alert"
  | "setup_review"
  | "watcher"
  | "market_watch"
  | "orchestration";

export type SignalReviewStatus =
  | "needs_review"
  | "validated"
  | "candidate_created"
  | "watching"
  | "important"
  | "ignored"
  | "read"
  | "unread"
  | "rejected"
  | "duplicate"
  | "other";

export type InboxSignalModel = {
  id: string;
  source: SignalSourceKind;
  symbol: string;
  direction?: string | null;
  timeframe?: string | null;
  title: string;
  summary: string;
  confidence: number | null;
  freshness: FreshnessState;
  freshnessLabel?: string;
  receivedAt: string | null;
  reviewStatus: SignalReviewStatus;
  provenance: string;
  href: string;
  nextAction: string;
  detailHref?: string;
  planHref?: string;
  validateHref?: string;
  canCreateDraft?: boolean;
  canPlanTrade?: boolean;
  canDismiss?: boolean;
  dismissTarget?: "setup_review" | "alert" | "session";
  rawAlertId?: string;
  tradingViewSignalId?: string;
};

export type PlanHierarchyModel = {
  proposalId: string | null;
  approvalId: string | null;
  symbol: string | null;
  direction: string | null;
  timeframe: string | null;
  thesis: string | null;
  entry: string | null;
  invalidation: string | null;
  stopLoss: string | null;
  takeProfit: string | null;
  riskSummary: string | null;
  size: string | null;
  approvalState: string;
  paperExecutionState: string;
  riskBlocked: boolean;
  blockReason: string | null;
  proposalHref: string | null;
  approvalHref: string | null;
  confidence: number | null;
};

export const ATTENTION_SECTION_ORDER: readonly AttentionSectionId[] = [
  "safety",
  "pending_decisions",
  "new_signals",
  "validation_work",
  "positions_risk",
  "lessons",
] as const;

export const ATTENTION_SECTION_LABELS: Record<AttentionSectionId, string> = {
  safety: "Safety and trading posture",
  pending_decisions: "Pending decisions",
  new_signals: "New signals requiring review",
  validation_work: "Active validation work",
  positions_risk: "Open paper positions or risk alerts",
  lessons: "Recent lessons or journal follow-ups",
};
