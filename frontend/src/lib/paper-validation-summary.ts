/**
 * Turn raw paper validation run state into a calm, human-readable summary so
 * traders can answer: is it running, what mode, did the last scan find
 * anything, was a trade opened, why was it skipped, and what to do next.
 */

import type {
  PaperEligibilityReport,
  PaperRuntimeHistoryRecord,
  PaperValidationRun,
} from "@/lib/api/types";

export interface PaperValidationView {
  running: boolean;
  modeLabel: string;
  statusLabel: string;
  lastScanSummary: string;
  tradeOpened: boolean;
  skipReason: string | null;
  nextAction: string;
}

const RUNNING_STATUSES = new Set(["running", "active", "in_progress"]);

function modeLabel(mode?: string): string {
  switch ((mode ?? "scan_only").toLowerCase()) {
    case "scan_only":
      return "Scan only (no simulated trades opened automatically)";
    case "scan_and_trade":
    case "auto":
      return "Scan and simulate trades";
    default:
      return mode ?? "Scan only";
  }
}

function latestSkipReason(history: PaperRuntimeHistoryRecord[]): string | null {
  const skipped = history.find((h) => h.reason && h.status !== "ok" && h.status !== "completed");
  return skipped?.reason ?? null;
}

export function buildPaperValidationView(
  run: PaperValidationRun | undefined | null,
  eligibility: PaperEligibilityReport | null,
  history: PaperRuntimeHistoryRecord[],
): PaperValidationView {
  if (!run) {
    const eligible = eligibility?.paper_eligible ?? false;
    return {
      running: false,
      modeLabel: "—",
      statusLabel: "Not started",
      lastScanSummary: "No scans yet.",
      tradeOpened: false,
      skipReason: eligible ? null : (eligibility?.blockers[0] ?? null),
      nextAction: eligible
        ? "Start paper validation to begin simulating this strategy."
        : "Resolve eligibility blockers before starting paper validation.",
    };
  }

  const running = RUNNING_STATUSES.has(run.status.toLowerCase());
  const scan = run.last_scan_result ?? null;
  const triggered = scan?.triggered === true;
  const tradeOpened = scan?.trade_created === true;
  const blockers = run.blockers ?? [];
  const skipReason = blockers[0] ?? latestSkipReason(history);

  let lastScanSummary: string;
  if (!run.last_scan_at) {
    lastScanSummary = "No scans yet — run a scan to check for setups.";
  } else if (tradeOpened) {
    lastScanSummary = "Latest scan found a setup and opened a simulated paper trade.";
  } else if (triggered) {
    lastScanSummary = "Latest scan found a setup signal (no simulated trade opened).";
  } else {
    lastScanSummary = "Latest scan ran but found no qualifying setup.";
  }

  let nextAction: string;
  if (!running) {
    nextAction = "Run is stopped — start a new run to continue validating.";
  } else if (skipReason) {
    nextAction = "Review the skip reason below, then run another scan.";
  } else if (run.metrics && run.metrics.paper_trades_count > 0) {
    nextAction = "Run ticks to update open trades, then review metrics.";
  } else {
    nextAction = "Run a scan to look for the next setup.";
  }

  return {
    running,
    modeLabel: modeLabel(run.runtime_mode),
    statusLabel: run.status,
    lastScanSummary,
    tradeOpened,
    skipReason,
    nextAction,
  };
}
