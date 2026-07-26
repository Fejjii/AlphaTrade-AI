import {
  ATTENTION_SECTION_ORDER,
  type AttentionItemModel,
  type AttentionSectionId,
} from "@/components/workflows/types";

export type AttentionBuildInput = {
  executionMode: string | null | undefined;
  realTradingEnabled: boolean | null | undefined;
  paperOnlyConfirmed: boolean;
  pendingApprovals: number;
  pendingProposals: number;
  unreadAlerts: number;
  unreviewedSetupAlerts: number;
  validatedSignalsNeedingReview: number;
  activeValidations: number;
  draftsReady: number;
  candidatesQueued: number;
  runPlansPending: number;
  openPaperPositions: number;
  riskAlertsActive: boolean;
  lossLockActive: boolean;
  greenDayProtectionActive: boolean;
  overtradingWarningActive: boolean;
  pendingLessons: number;
  nextAction?: { action: string; reason?: string; link?: string } | null;
};

const SECTION_PRIORITY: Record<AttentionSectionId, AttentionItemModel["priority"]> = {
  safety: 1,
  pending_decisions: 2,
  new_signals: 3,
  validation_work: 4,
  positions_risk: 5,
  lessons: 6,
};

function pushItem(
  items: AttentionItemModel[],
  item: Omit<AttentionItemModel, "priority"> & { priority?: AttentionItemModel["priority"] },
): void {
  items.push({
    ...item,
    priority: item.priority ?? SECTION_PRIORITY[item.section],
  });
}

/**
 * Build a prioritized attention queue from existing dashboard/API facts only.
 * Empty sections are omitted so the UI can render honest empty states.
 */
export function buildAttentionItems(input: AttentionBuildInput): AttentionItemModel[] {
  const items: AttentionItemModel[] = [];

  // Safety section only surfaces actionable posture problems (not a green status card).
  if (!input.paperOnlyConfirmed) {
    pushItem(items, {
      id: "safety-unverified",
      section: "safety",
      title: "Safety posture needs confirmation",
      summary: "Paper-only posture is not confirmed. Review Settings before acting.",
      href: "/settings",
      actionLabel: "Review settings",
      tone: "danger",
    });
  }

  if (input.lossLockActive) {
    pushItem(items, {
      id: "safety-loss-lock",
      section: "safety",
      title: "Daily loss lock is active",
      summary: "New paper entries may be restricted until the lock clears.",
      href: "/risk",
      actionLabel: "Open risk state",
      tone: "danger",
    });
  } else if (input.greenDayProtectionActive || input.overtradingWarningActive) {
    pushItem(items, {
      id: "safety-protection",
      section: "safety",
      title: input.greenDayProtectionActive
        ? "Green-day protection engaged"
        : "Overtrading warning active",
      summary: "Protective paper-trading signals are active for today.",
      href: "/risk",
      actionLabel: "Review risk",
      tone: "warning",
    });
  }

  if (input.pendingApprovals > 0) {
    pushItem(items, {
      id: "pending-approvals",
      section: "pending_decisions",
      title: "Approvals awaiting your decision",
      summary: `${input.pendingApprovals} paper approval${input.pendingApprovals === 1 ? "" : "s"} pending.`,
      href: "/approvals",
      actionLabel: "Review approvals",
      tone: "warning",
      count: input.pendingApprovals,
    });
  }

  if (input.pendingProposals > 0) {
    pushItem(items, {
      id: "pending-proposals",
      section: "pending_decisions",
      title: "Trade proposals need review",
      summary: `${input.pendingProposals} proposal${input.pendingProposals === 1 ? "" : "s"} awaiting approval.`,
      href: "/proposals",
      actionLabel: "Open proposals",
      count: input.pendingProposals,
    });
  }

  if (input.nextAction?.link && input.nextAction.action) {
    pushItem(items, {
      id: "next-recommended-action",
      section: "pending_decisions",
      title: input.nextAction.action,
      summary: input.nextAction.reason ?? "Recommended next step from dashboard summary.",
      href: input.nextAction.link,
      actionLabel: "Continue",
      tone: "info",
    });
  }

  if (input.unreviewedSetupAlerts > 0) {
    pushItem(items, {
      id: "setup-alerts-unreviewed",
      section: "new_signals",
      title: "Setup alerts need triage",
      summary: `${input.unreviewedSetupAlerts} unreviewed setup alert${
        input.unreviewedSetupAlerts === 1 ? "" : "s"
      }.`,
      href: "/alerts/review",
      actionLabel: "Review setup alerts",
      tone: "warning",
      count: input.unreviewedSetupAlerts,
    });
  }

  if (input.validatedSignalsNeedingReview > 0) {
    pushItem(items, {
      id: "tv-signals-review",
      section: "new_signals",
      title: "TradingView signals ready for review",
      summary: `${input.validatedSignalsNeedingReview} validated signal${
        input.validatedSignalsNeedingReview === 1 ? "" : "s"
      } without a paper candidate.`,
      href: "/tradingview-signals",
      actionLabel: "Open signals inbox",
      count: input.validatedSignalsNeedingReview,
    });
  }

  if (input.unreadAlerts > 0) {
    pushItem(items, {
      id: "unread-alerts",
      section: "new_signals",
      title: "Unread in-app alerts",
      summary: `${input.unreadAlerts} unread alert${input.unreadAlerts === 1 ? "" : "s"} (alerts never trade).`,
      href: "/alerts",
      actionLabel: "Open alerts",
      count: input.unreadAlerts,
    });
  }

  if (input.activeValidations > 0) {
    pushItem(items, {
      id: "active-validations",
      section: "validation_work",
      title: "Active paper validations",
      summary: `${input.activeValidations} strategy validation${
        input.activeValidations === 1 ? "" : "s"
      } running.`,
      href: "/paper-validation/run-sessions",
      actionLabel: "View sessions",
      count: input.activeValidations,
    });
  }

  if (input.draftsReady > 0) {
    pushItem(items, {
      id: "drafts-ready",
      section: "validation_work",
      title: "Paper drafts ready for validation",
      summary: `${input.draftsReady} draft${input.draftsReady === 1 ? "" : "s"} marked ready.`,
      href: "/paper-validation/drafts",
      actionLabel: "Open drafts",
      count: input.draftsReady,
    });
  }

  if (input.candidatesQueued > 0) {
    pushItem(items, {
      id: "candidates-queued",
      section: "validation_work",
      title: "Validation candidates queued",
      summary: `${input.candidatesQueued} candidate${input.candidatesQueued === 1 ? "" : "s"} waiting.`,
      href: "/paper-validation/candidates",
      actionLabel: "Open queue",
      count: input.candidatesQueued,
    });
  }

  if (input.runPlansPending > 0) {
    pushItem(items, {
      id: "run-plans-pending",
      section: "validation_work",
      title: "Run plans need attention",
      summary: `${input.runPlansPending} planned run${input.runPlansPending === 1 ? "" : "s"}.`,
      href: "/paper-validation/run-plans",
      actionLabel: "Open run plans",
      count: input.runPlansPending,
    });
  }

  if (input.openPaperPositions > 0) {
    pushItem(items, {
      id: "open-positions",
      section: "positions_risk",
      title: "Open paper positions",
      summary: `${input.openPaperPositions} open paper position${
        input.openPaperPositions === 1 ? "" : "s"
      }.`,
      href: "/positions",
      actionLabel: "View positions",
      count: input.openPaperPositions,
    });
  }

  if (input.riskAlertsActive) {
    pushItem(items, {
      id: "risk-alerts",
      section: "positions_risk",
      title: "Risk posture needs attention",
      summary: "Protective risk signals are active for paper trading.",
      href: "/risk",
      actionLabel: "Open risk",
      tone: "warning",
    });
  }

  if (input.pendingLessons > 0) {
    pushItem(items, {
      id: "pending-lessons",
      section: "lessons",
      title: "Lessons awaiting review",
      summary: `${input.pendingLessons} lesson${input.pendingLessons === 1 ? "" : "s"} pending.`,
      href: "/lessons",
      actionLabel: "Review lessons",
      count: input.pendingLessons,
    });
  }

  return sortAttentionItems(items);
}

export function sortAttentionItems(items: AttentionItemModel[]): AttentionItemModel[] {
  const sectionRank = new Map(
    ATTENTION_SECTION_ORDER.map((section, index) => [section, index] as const),
  );
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      if (a.item.priority !== b.item.priority) return a.item.priority - b.item.priority;
      const sectionDelta =
        (sectionRank.get(a.item.section) ?? 99) - (sectionRank.get(b.item.section) ?? 99);
      if (sectionDelta !== 0) return sectionDelta;
      // Preserve builder insertion order within a section (stable, no id inventiveness).
      return a.index - b.index;
    })
    .map(({ item }) => item);
}

export function groupAttentionItems(
  items: AttentionItemModel[],
): Array<{ section: AttentionSectionId; items: AttentionItemModel[] }> {
  return ATTENTION_SECTION_ORDER.map((section) => ({
    section,
    items: items.filter((item) => item.section === section),
  })).filter((group) => group.items.length > 0);
}
