import type {
  WatcherMonitoringRuntimeState,
  WatcherMonitoringSnapshot,
} from "@/lib/api/types";

export type WatcherStatusTone = "healthy" | "muted" | "warn" | "stale" | "blocked";

/** Map API runtime state to badge tone. Never derive RUNNING from config flags. */
export function watcherStatusTone(state: WatcherMonitoringRuntimeState): WatcherStatusTone {
  if (state === "RUNNING") return "healthy";
  if (state === "STOPPED") return "muted";
  if (state === "DEGRADED") return "warn";
  if (state === "STALE") return "stale";
  return "blocked";
}

export function watcherStatusLabel(state: WatcherMonitoringRuntimeState): string {
  return state;
}

/**
 * Operator-visible runtime state comes only from the typed API snapshot.
 * Configuration flags must not be treated as RUNNING.
 */
export function displayedWatcherStatus(
  snapshot: WatcherMonitoringSnapshot,
): WatcherMonitoringRuntimeState {
  return snapshot.watcher_status;
}

export function paperMonitoringActive(snapshot: WatcherMonitoringSnapshot): boolean {
  return (
    snapshot.paper_posture.paper_only &&
    snapshot.paper_posture.runtime_evidence &&
    snapshot.watcher_status !== "STOPPED" &&
    snapshot.watcher_status !== "BLOCKED"
  );
}

export function formatReasonCode(code: string): string {
  return code.replace(/_/g, " ");
}
