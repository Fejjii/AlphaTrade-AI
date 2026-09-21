import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DecisionStrategyPage from "./page";

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchStatus: { active: false, execution_blocked: false },
  }),
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    postureKnown: true,
  }),
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      quality: {
        data: {
          total_detectors: 4,
          detectors_with_data: 2,
          total_results: 9,
          ranked: [
            {
              condition: "liquidity_sweep",
              rank: 1,
              quality_score: 0.7,
              sample_size: 12,
              trust_tier: "medium",
              verdict: "watch",
            },
          ],
        },
        available: true,
      },
      learning: {
        data: {
          completed_sessions: 3,
          results_count: 3,
          lessons_count: 1,
        },
        available: true,
      },
      setups: {
        data: {
          setups: [
            {
              setup_type: "htf_trend_pullback",
              proposal_count: 2,
              paper_trade_count: 2,
              winning_paper_trades: 1,
              losing_paper_trades: 1,
              most_common_mistakes: [],
              most_common_lessons: [],
            },
          ],
        },
        available: true,
      },
      canonical: {
        data: {
          authority: "canonical",
          snapshot: {
            organization_id: "org",
            patterns: [],
            human_vs_system: {
              human_reject_or_skip: 0,
              human_approvals: 2,
              paper_system_executions: 1,
              executed_outcomes: 1,
              setup_confirmed_count: 2,
            },
          },
        },
        available: true,
      },
      evaluation: {
        data: {
          authority: "canonical",
          live_executable: false,
          watcher_activated: false,
          summary: {
            organization_id: "org",
            authority: "paper_evaluation_measurement",
            live_executable: false,
            facts: {
              watcher: {
                scan_count: 0,
                confirmed_setup_count: 0,
                candidates_published: 0,
                stale_evidence_count: 0,
                provider_outage_count: 0,
              },
              conversion: {
                scans: 0,
                assessments: 2,
                confirmed_setups: 2,
                candidates: 2,
                eligible: 1,
                blocked: 0,
                approved: 2,
                rejected: 0,
                skipped: 0,
                filled: 1,
                closed: 1,
              },
              false_signals: {
                confirmed_losses: 0,
                executed_outcomes: 1,
                false_signal_rate: "0",
              },
              strategy_overall: {
                win_rate: "1",
                expectancy: "10",
                max_drawdown: "0",
                average_mfe: "20",
                average_mae: "5",
                executed_outcome_count: 1,
                confidence: "insufficient",
              },
              rule_adherence: {
                risk_adhered_count: 1,
                stop_violation_count: 0,
                adherence_rate: "1",
              },
              blocked: { blocked_count: 0, by_reason: [] },
              human_vs_system: {
                human_reject_or_skip: 0,
                human_approvals: 2,
                paper_system_executions: 1,
                executed_outcomes: 1,
              },
              missed_opportunities: {
                rejected_confirmed: 0,
                skipped_confirmed: 0,
                eligible_not_approved: 0,
                blocked_after_confirmation: 0,
                counterfactual_pnl: null,
                warning:
                  "Missed-opportunity counts are funnel misses only. Counterfactual PnL is not invented.",
              },
              data_quality: {
                fresh_count: 0,
                stale_count: 0,
                unavailable_count: 0,
                replay_count: 0,
                stale_or_unavailable_rate: null,
              },
              warnings: [],
            },
            refinements: [],
            narrative: null,
          },
        },
        available: true,
      },
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("Strategy performance page", () => {
  afterEach(() => cleanup());

  it("renders existing strategy and pattern APIs without promotion claims", () => {
    render(<DecisionStrategyPage />);
    expect(screen.getByTestId("strategy-performance")).toHaveTextContent("liquidity_sweep");
    expect(screen.getByText(/no automatic rule promotion/i)).toBeInTheDocument();
    expect(screen.getByTestId("paper-evaluation-summary")).toHaveTextContent(
      /refinements are suggestions/i,
    );
  });
});
