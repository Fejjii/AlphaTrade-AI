import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";

const baseProps = {
  summary: {
    strategy_id: "s1",
    paper_eligible: true,
    runs: [
      {
        id: "run1",
        strategy_id: "s1",
        status: "in_progress",
        runtime_mode: "scan_only",
        paper_eligible: true,
        blockers: ["Need more samples"],
        metrics: {
          paper_trades_count: 2,
          win_rate: 0.5,
          net_pnl: "10",
          profit_factor: 1.2,
          expectancy: "5",
          max_drawdown_pct: 3.5,
        },
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    ],
    total: 1,
  },
  eligibility: {
    strategy_id: "s1",
    status: "paper_eligible",
    paper_eligible: true,
    recommendation: "continue",
    testability_score: 80,
    limitations: ["Paper only"],
    eligibility_reasons: [],
    blockers: [],
    real_trading_enabled: false,
    accepted_lessons: [],
    unresolved_lesson_candidates: [],
  },
  scheduler: {
    env_enabled: false,
    tenant_enabled: false,
    effective_enabled: false,
    config: {
      enabled: false,
      interval_seconds: 300,
      max_runs_per_cycle: 5,
      max_scans_per_minute: 10,
    },
    real_trading_enabled: false,
    limitation: "Paper only",
  },
  history: [
    {
      id: "h1",
      mode: "scan",
      status: "success",
      started_at: "2024-01-01T00:00:00Z",
      signals_created: 1,
      trades_opened: 0,
      trades_closed: 0,
      blockers: [],
      warnings: ["Provider reported stale data."],
      data_freshness: "stale",
    },
  ],
  alerts: [
    {
      id: "a1",
      alert_type: "setup_signal_detected",
      severity: "info",
      message: "Signal detected",
      created_at: "2024-01-01T00:00:00Z",
    },
  ],
  busy: false,
  signals: [],
  trades: [],
  onStart: vi.fn(),
  onScan: vi.fn(),
  onTick: vi.fn(),
  onStop: vi.fn(),
  onSchedulerTick: vi.fn(),
  onMarkAlertRead: vi.fn(),
};

describe("PaperValidationPanel slice 40", () => {
  it("renders scheduler, history, alerts, and disclaimer", () => {
    render(<PaperValidationPanel {...baseProps} />);

    expect(screen.getByTestId("paper-only-disclaimer")).toBeInTheDocument();
    expect(screen.getByTestId("scheduler-status")).toBeInTheDocument();
    expect(screen.getByTestId("last-scheduler-tick")).toBeInTheDocument();
    expect(screen.getByTestId("manual-scheduler-tick")).toBeInTheDocument();
    expect(screen.getByTestId("runtime-history")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-alerts")).toBeInTheDocument();
    expect(screen.getByTestId("paper-validation-blockers")).toBeInTheDocument();
    expect(screen.getByTestId("data-freshness-warning")).toBeInTheDocument();
    expect(screen.getByTestId("mark-alert-read-a1")).toBeInTheDocument();
  });
});
