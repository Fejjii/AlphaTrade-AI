import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WatcherMonitoringCard } from "@/components/WatcherMonitoringCard";
import { makeWatcherMonitoringSnapshot } from "@/lib/watcher-monitoring-fixtures";
import { displayedWatcherStatus } from "@/lib/watcher-monitoring";

afterEach(cleanup);

describe("WatcherMonitoringCard", () => {
  it("shows loading-independent empty stopped state without fake activity", () => {
    render(<WatcherMonitoringCard snapshot={makeWatcherMonitoringSnapshot()} />);
    expect(screen.getByTestId("watcher-monitoring-card")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-monitoring-status-row")).toHaveTextContent("STOPPED");
    expect(screen.getByText("Paper only")).toBeInTheDocument();
    expect(screen.getByText("Real trading OFF")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-monitoring-candidates")).toHaveTextContent("None");
    expect(screen.getByTestId("watcher-monitoring-assessments")).toHaveTextContent("None persisted");
    expect(screen.getByTestId("watcher-monitoring-next-scan")).toHaveTextContent("—");
    expect(screen.getByTestId("watcher-monitoring-last-scan")).toHaveTextContent("never");
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });

  it("does not infer RUNNING from frontend configuration flags", () => {
    const snapshot = makeWatcherMonitoringSnapshot({
      watcher_status: "STOPPED",
      paper_monitoring_status: "STOPPED",
      config_flags: {
        market_watcher_enabled: true,
        watcher_orchestration_enabled: true,
        worker_enabled: true,
        market_watcher_bridge_enabled: true,
        market_watcher_bridge_auto_tick: true,
        telegram_alerts_enabled: false,
        telegram_interaction_enabled: false,
        automatic_telegram_delivery_enabled: false,
      },
    });
    expect(displayedWatcherStatus(snapshot)).toBe("STOPPED");
    render(<WatcherMonitoringCard snapshot={snapshot} />);
    expect(screen.getByTestId("watcher-monitoring-status-row")).toHaveTextContent("STOPPED");
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });

  it("renders running with runtime evidence, next scan, and no fake prices", () => {
    render(
      <WatcherMonitoringCard
        snapshot={makeWatcherMonitoringSnapshot({
          watcher_status: "RUNNING",
          paper_monitoring_status: "RUNNING",
          reason_code: "healthy",
          warnings: [],
          paper_posture: {
            paper_only: true,
            execution_mode: "paper",
            real_trading_enabled: false,
            kill_switch_blocked: false,
            telegram_enabled: false,
            watcher_config_enabled: true,
            runtime_evidence: true,
          },
          last_scan_at: "2026-09-21T13:55:00.000Z",
          last_scan_status: "ok",
          next_scan_at: "2026-09-21T14:00:30.000Z",
          next_scan_basis: "lease_ttl",
          leases: [
            {
              scan_scope: "paper-monitor",
              owner_id: "worker-1",
              lease_epoch: 1,
              fencing_token: 1,
              fenced: true,
              heartbeat_fresh: true,
              orchestration_state: "healthy",
              reason_code: "healthy",
            },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("watcher-monitoring-status-row")).toHaveTextContent("RUNNING");
    expect(screen.getByText("Runtime evidence")).toBeInTheDocument();
    expect(screen.getByTestId("watcher-monitoring-next-scan")).not.toHaveTextContent(/^—$/);
    expect(screen.queryByText(/91234/)).not.toBeInTheDocument();
  });

  it("renders degraded provider outage and recent errors", () => {
    render(
      <WatcherMonitoringCard
        snapshot={makeWatcherMonitoringSnapshot({
          watcher_status: "DEGRADED",
          paper_monitoring_status: "DEGRADED",
          reason_code: "provider_unavailable",
          paper_posture: {
            paper_only: true,
            execution_mode: "paper",
            real_trading_enabled: false,
            kill_switch_blocked: false,
            telegram_enabled: false,
            watcher_config_enabled: true,
            runtime_evidence: true,
          },
          provider_health: [
            {
              name: "mock-market-data",
              kind: "market_data",
              health: "unavailable",
              using_fallback: false,
              is_mock: true,
              error_message: "upstream timeout",
            },
          ],
          recent_errors: [
            {
              source: "provider:mock-market-data",
              message: "upstream timeout",
              reason_code: "unavailable",
            },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("watcher-monitoring-status-row")).toHaveTextContent("DEGRADED");
    expect(screen.getByTestId("watcher-monitoring-providers")).toHaveTextContent("unavailable");
    expect(screen.getByTestId("watcher-monitoring-errors")).toHaveTextContent("upstream timeout");
  });

  it("renders stale market freshness", () => {
    render(
      <WatcherMonitoringCard
        snapshot={makeWatcherMonitoringSnapshot({
          watcher_status: "STALE",
          paper_monitoring_status: "STALE",
          reason_code: "market_data_stale",
          market_freshness: {
            status: "stale",
            symbol: "BTCUSDT",
            observed_at: "2026-09-21T11:00:00.000Z",
            data_freshness: "stale",
            stale_after_minutes: 60,
          },
        })}
      />,
    );
    expect(screen.getByTestId("watcher-monitoring-status-row")).toHaveTextContent("STALE");
    expect(screen.getByTestId("watcher-monitoring-freshness")).toHaveTextContent("stale");
  });

  it("renders blocked reasons and paper safety", () => {
    render(
      <WatcherMonitoringCard
        snapshot={makeWatcherMonitoringSnapshot({
          watcher_status: "BLOCKED",
          paper_monitoring_status: "BLOCKED",
          reason_code: "kill_switch_active",
          block_reasons: ["kill_switch_active"],
        })}
      />,
    );
    expect(screen.getByTestId("watcher-monitoring-status-row")).toHaveTextContent("BLOCKED");
    expect(screen.getByTestId("watcher-monitoring-block-reasons")).toHaveTextContent("kill switch active");
    expect(screen.getByText("Paper only")).toBeInTheDocument();
  });

  it("renders no approved strategies and candidate detected facts", () => {
    render(
      <WatcherMonitoringCard
        snapshot={makeWatcherMonitoringSnapshot({
          approved_strategies: [],
          warnings: ["no_approved_strategies"],
          scanner_candidates: {
            count: 2,
            conditions: ["liquidity_sweep", "sfp"],
            last_scan_at: "2026-09-21T13:55:00.000Z",
            source: "market_watcher_scan",
          },
          setup_assessments: [
            {
              assessment_id: "a1",
              candidate_id: "c1",
              state: "confirmed_setup",
              strategy_version_id: "sv1",
              instrument: "BINANCE:PERP:BTCUSDT",
              timeframe: "1h",
              valid_until: "2026-09-21T15:00:00.000Z",
              live_executable: false,
            },
          ],
        })}
      />,
    );
    expect(screen.getByTestId("watcher-monitoring-strategies")).toHaveTextContent("None approved");
    expect(screen.getByTestId("watcher-monitoring-warnings")).toHaveTextContent("no approved strategies");
    expect(screen.getByTestId("watcher-monitoring-candidates")).toHaveTextContent("2");
    expect(screen.getByTestId("watcher-monitoring-assessments")).toHaveTextContent("confirmed_setup");
  });

  it("supports compact mobile layout and refresh", () => {
    const onRefresh = vi.fn();
    render(
      <WatcherMonitoringCard
        snapshot={makeWatcherMonitoringSnapshot()}
        compact
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getByTestId("watcher-monitoring-refresh"));
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: /watcher scanner/i })).toHaveAttribute("href", "/watcher");
  });
});
