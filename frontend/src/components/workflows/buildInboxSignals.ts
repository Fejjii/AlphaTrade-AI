import { freshnessFromTimestamp } from "@/components/workflows/freshness";
import { buildPlanHref } from "@/components/workflows/planContext";
import type { InboxSignalModel, SignalReviewStatus } from "@/components/workflows/types";
import type {
  MarketWatcherSummary,
  PaperAlert,
  SetupAlertReviewItem,
  TradingViewSignalItem,
} from "@/lib/api/types";

export type InboxSignalsInput = {
  tradingViewSignals?: TradingViewSignalItem[];
  alerts?: PaperAlert[];
  setupReviews?: SetupAlertReviewItem[];
  watcherSummary?: MarketWatcherSummary | null;
  sessionDismissedIds?: ReadonlySet<string>;
  nowMs?: number;
};

function tvReviewStatus(signal: TradingViewSignalItem): SignalReviewStatus {
  switch (signal.status) {
    case "validated":
      return signal.links.candidate_id ? "candidate_created" : "needs_review";
    case "candidate_created":
      return "candidate_created";
    case "rejected":
      return "rejected";
    case "duplicate":
      return "duplicate";
    default:
      return "other";
  }
}

function setupReviewStatus(status: SetupAlertReviewItem["review_status"]): SignalReviewStatus {
  switch (status) {
    case "unreviewed":
      return "needs_review";
    case "watching":
      return "watching";
    case "important":
      return "important";
    case "ignored":
      return "ignored";
    default:
      return "other";
  }
}

/**
 * Consolidate signal-like rows from existing APIs into one inbox model.
 * Distinguishes live/delayed/stale/fallback/unavailable from real timestamps only.
 */
export function buildInboxSignals(input: InboxSignalsInput): InboxSignalModel[] {
  const nowMs = input.nowMs ?? Date.now();
  const dismissed = input.sessionDismissedIds ?? new Set<string>();
  const items: InboxSignalModel[] = [];

  for (const signal of input.tradingViewSignals ?? []) {
    const id = `tv:${signal.id}`;
    if (dismissed.has(id)) continue;
    const freshness =
      freshnessFromTimestamp(signal.received_at, { nowMs }) ?? {
        state: "unavailable" as const,
      };
    const reviewStatus = tvReviewStatus(signal);
    const needsCandidate = reviewStatus === "needs_review";
    items.push({
      id,
      source: "tradingview",
      symbol: signal.symbol,
      direction: signal.direction,
      timeframe: signal.timeframe,
      title: `${signal.symbol} · ${signal.direction}`,
      summary: signal.setup_name
        ? `${signal.setup_name}${signal.setup_version != null ? ` v${signal.setup_version}` : ""}`
        : "TradingView signed webhook signal",
      confidence: signal.confidence,
      freshness: freshness.state,
      freshnessLabel: freshness.ageLabel,
      receivedAt: signal.received_at,
      reviewStatus,
      provenance: `TradingView · alert ${signal.external_alert_id}`,
      href: `/tradingview-signals?signal=${signal.id}`,
      detailHref: `/tradingview-signals?signal=${signal.id}`,
      planHref: buildPlanHref({ source: "tradingview", signalId: signal.id }),
      validateHref: signal.links.paper_candidate_path ?? "/paper-validation/drafts",
      nextAction: needsCandidate
        ? "Create paper candidate"
        : reviewStatus === "candidate_created"
          ? "Open paper candidate"
          : "Inspect signal",
      canCreateDraft: needsCandidate,
      createActionLabel: needsCandidate ? "Create paper candidate" : undefined,
      canPlanTrade: true,
      canDismissWithReason: false,
      canHideForSession: true,
      dismissTarget: "session",
      tradingViewSignalId: signal.id,
    });
  }

  for (const review of input.setupReviews ?? []) {
    const id = `setup:${review.alert_id}`;
    if (dismissed.has(id) || review.review_status === "ignored") continue;
    const freshness =
      freshnessFromTimestamp(review.created_at, { nowMs }) ?? {
        state: "unavailable" as const,
      };
    const reviewStatus = setupReviewStatus(review.review_status);
    items.push({
      id,
      source: "setup_review",
      symbol: review.symbol ?? "—",
      direction: review.direction,
      timeframe: review.timeframe,
      title: `${review.symbol ?? "Setup"} · ${review.condition ?? "alert"}`,
      summary: review.reason ?? "Setup alert awaiting human triage",
      confidence: review.confidence ?? null,
      freshness: freshness.state,
      freshnessLabel: freshness.ageLabel,
      receivedAt: review.created_at,
      reviewStatus,
      provenance: `Setup review · ${review.delivery_channel}/${review.delivery_status}`,
      href: "/alerts/review",
      detailHref: "/alerts/review",
      planHref: buildPlanHref({ source: "setup_review", alertId: review.alert_id }),
      validateHref: "/alerts/review",
      nextAction: reviewStatus === "needs_review" ? "Review evidence" : "Open setup review",
      canCreateDraft: true,
      createActionLabel: "Create validation draft",
      canPlanTrade: true,
      canDismissWithReason: true,
      canHideForSession: false,
      dismissTarget: "setup_review",
      rawAlertId: review.alert_id,
    });
  }

  for (const alert of input.alerts ?? []) {
    const id = `alert:${alert.id}`;
    if (dismissed.has(id) || alert.read_at) continue;
    const freshness =
      freshnessFromTimestamp(alert.created_at, { nowMs }) ?? {
        state: "unavailable" as const,
      };
    items.push({
      id,
      source: "alert",
      symbol: alert.strategy_id ? "Strategy alert" : "Alert",
      direction: null,
      timeframe: null,
      title: alert.alert_type,
      summary: alert.message,
      confidence: null,
      freshness: freshness.state,
      freshnessLabel: freshness.ageLabel,
      receivedAt: alert.created_at,
      reviewStatus: "unread",
      provenance: `In-app alert · ${alert.alert_source ?? "unknown source"}`,
      href: "/alerts",
      detailHref: "/alerts",
      planHref: buildPlanHref({ source: "alert", alertId: alert.id }),
      nextAction: "Review evidence",
      canCreateDraft: false,
      canPlanTrade: false,
      canDismissWithReason: true,
      canHideForSession: false,
      dismissTarget: "alert",
      rawAlertId: alert.id,
    });
  }

  const watcher = input.watcherSummary;
  if (watcher?.last_scan_at) {
    const freshness =
      freshnessFromTimestamp(watcher.last_scan_at, { nowMs }) ?? {
        state: "unavailable" as const,
      };
    items.push({
      id: "watcher:summary",
      source: "watcher",
      symbol: "Watcher",
      title: "Market watcher scan",
      summary: `Last scan ${watcher.last_scan_status ?? "unknown"} · ${
        watcher.last_scan_candidate_count ?? 0
      } candidates`,
      confidence: null,
      freshness: freshness.state,
      freshnessLabel: freshness.ageLabel,
      receivedAt: watcher.last_scan_at,
      reviewStatus: "other",
      provenance: "Watcher scanner (read-only)",
      href: "/watcher",
      detailHref: "/watcher",
      nextAction: "Open watcher scanner",
      canCreateDraft: false,
      canPlanTrade: false,
      canDismissWithReason: false,
      canHideForSession: false,
    });
  }

  return items.sort((a, b) => {
    const aNeeds = a.reviewStatus === "needs_review" || a.reviewStatus === "unread" ? 0 : 1;
    const bNeeds = b.reviewStatus === "needs_review" || b.reviewStatus === "unread" ? 0 : 1;
    if (aNeeds !== bNeeds) return aNeeds - bNeeds;
    const aTime = a.receivedAt ? new Date(a.receivedAt).getTime() : 0;
    const bTime = b.receivedAt ? new Date(b.receivedAt).getTime() : 0;
    return bTime - aTime;
  });
}
