/**
 * Presentation helpers for paper validation alerts: human-readable titles,
 * source labels, severity ordering, and a calm suggested next action.
 */

import type { StrategyBadgeVariant } from "@/lib/strategy-status";

const ALERT_TYPE_LABELS: Record<string, string> = {
  setup_signal_detected: "Setup signal detected",
  paper_trade_opened: "Paper trade opened",
  paper_trade_closed: "Paper trade closed",
  stop_hit: "Stop hit",
  tp_hit: "Take profit hit",
  runner_exit: "Runner exit",
  data_stale: "Market data is stale",
  strategy_blocked: "Strategy blocked",
  promotion_status_changed: "Promotion status changed",
  paper_validation_restricted: "Paper validation restricted",
  overtrading_warning: "Trading frequency notice",
  daily_loss_lock_warning: "Daily loss protection notice",
};

export function alertTypeLabel(type: string): string {
  return ALERT_TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

const ALERT_SOURCE_LABELS: Record<string, string> = {
  paper_validation_runtime: "Paper validation",
  market_watcher: "Market watcher",
  market_watcher_bridge: "Market watcher bridge",
  manual_action: "Manual action",
};

export function alertSourceLabel(source: string | undefined): string {
  if (!source) return "Paper validation";
  return ALERT_SOURCE_LABELS[source] ?? source.replace(/_/g, " ");
}

export function severityVariant(severity: string): StrategyBadgeVariant {
  switch (severity.toLowerCase()) {
    case "critical":
      return "danger";
    case "warning":
      return "warning";
    case "info":
      return "info";
    default:
      return "muted";
  }
}

/** Higher = more urgent; used to sort alerts so critical surfaces first. */
export function severityRank(severity: string): number {
  switch (severity.toLowerCase()) {
    case "critical":
      return 3;
    case "warning":
      return 2;
    case "info":
      return 1;
    default:
      return 0;
  }
}

const NEXT_ACTION_BY_TYPE: Record<string, string> = {
  setup_signal_detected: "Open the strategy to review the setup. Alerts never place trades.",
  paper_trade_opened: "Track the simulated trade in paper validation.",
  paper_trade_closed: "Review the closed simulated trade and its metrics.",
  data_stale: "Treat results cautiously until fresh market data returns.",
  strategy_blocked: "Open the strategy to resolve the blocker.",
  paper_validation_restricted: "Review blockers before retrying paper validation.",
  overtrading_warning: "Consider pausing — frequent entries can reduce discipline.",
  daily_loss_lock_warning: "Consider stepping back for the day to protect capital.",
};

export function alertNextAction(type: string): string {
  return NEXT_ACTION_BY_TYPE[type] ?? "Review the alert details. Alerts never execute trades.";
}
