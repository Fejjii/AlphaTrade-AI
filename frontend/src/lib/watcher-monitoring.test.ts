import { describe, expect, it } from "vitest";

import { makeWatcherMonitoringSnapshot } from "@/lib/watcher-monitoring-fixtures";
import {
  displayedWatcherStatus,
  paperMonitoringActive,
  watcherStatusTone,
} from "@/lib/watcher-monitoring";

describe("watcher monitoring display helpers", () => {
  it("never treats config flags as RUNNING", () => {
    const snapshot = makeWatcherMonitoringSnapshot({
      watcher_status: "STOPPED",
      config_flags: {
        market_watcher_enabled: true,
        watcher_orchestration_enabled: true,
        worker_enabled: true,
        market_watcher_bridge_enabled: false,
        market_watcher_bridge_auto_tick: false,
        telegram_alerts_enabled: false,
        telegram_interaction_enabled: false,
        automatic_telegram_delivery_enabled: false,
      },
    });
    expect(displayedWatcherStatus(snapshot)).toBe("STOPPED");
    expect(paperMonitoringActive(snapshot)).toBe(false);
    expect(watcherStatusTone(snapshot.watcher_status)).toBe("muted");
  });

  it("maps runtime states to honest tones", () => {
    expect(watcherStatusTone("RUNNING")).toBe("healthy");
    expect(watcherStatusTone("STOPPED")).toBe("muted");
    expect(watcherStatusTone("DEGRADED")).toBe("warn");
    expect(watcherStatusTone("STALE")).toBe("stale");
    expect(watcherStatusTone("BLOCKED")).toBe("blocked");
  });

  it("treats paper monitoring as active only with runtime evidence", () => {
    expect(
      paperMonitoringActive(
        makeWatcherMonitoringSnapshot({
          watcher_status: "RUNNING",
          paper_posture: {
            paper_only: true,
            execution_mode: "paper",
            real_trading_enabled: false,
            kill_switch_blocked: false,
            telegram_enabled: false,
            watcher_config_enabled: true,
            runtime_evidence: true,
          },
        }),
      ),
    ).toBe(true);
    expect(
      paperMonitoringActive(
        makeWatcherMonitoringSnapshot({
          watcher_status: "RUNNING",
          paper_posture: {
            paper_only: true,
            execution_mode: "paper",
            real_trading_enabled: false,
            kill_switch_blocked: false,
            telegram_enabled: false,
            watcher_config_enabled: true,
            runtime_evidence: false,
          },
        }),
      ),
    ).toBe(false);
  });
});
