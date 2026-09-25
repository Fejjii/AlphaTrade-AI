import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PaperEvaluationSummaryCard } from "./PaperEvaluationSummaryCard";
import type { CanonicalPaperEvaluationRead } from "@/lib/api/types";

function evaluation(): CanonicalPaperEvaluationRead {
  return {
    authority: "canonical",
    live_executable: false,
    watcher_activated: false,
    summary: {
      organization_id: "org",
      authority: "paper_evaluation_measurement",
      live_executable: false,
      facts: {
        watcher: {
          scan_count: 3,
          confirmed_setup_count: 1,
          candidates_published: 1,
          stale_evidence_count: 0,
          provider_outage_count: 0,
        },
        conversion: {
          scans: 3,
          assessments: 1,
          confirmed_setups: 1,
          candidates: 1,
          eligible: 1,
          blocked: 0,
          approved: 1,
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
          win_count: 1,
          loss_count: 0,
          net_pnl_total: "10",
          confidence: "insufficient",
        },
        strategy_versions: [
          {
            strategy_version_id: "strategy-1",
            setup_definition_id: "setup-1",
            executed_outcome_count: 1,
            win_count: 1,
            loss_count: 0,
            win_rate: "1",
            net_pnl_total: "10",
          },
        ],
        rule_adherence: {
          risk_adhered_count: 1,
          stop_violation_count: 0,
          adherence_rate: "1",
        },
        blocked: { blocked_count: 0, by_reason: [] },
        human_vs_system: {
          human_reject_or_skip: 0,
          human_approvals: 1,
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
          fresh_count: 3,
          stale_count: 0,
          unavailable_count: 0,
          replay_count: 0,
          stale_or_unavailable_rate: "0",
        },
        warnings: [{ code: "watcher_not_activated", message: "Watcher stays off." }],
      },
      refinements: [
        {
          suggestion_id: "sug-1",
          category: "false_signal",
          summary: "Review trigger tightness. Suggestion only.",
          severity: "high",
          activate: false,
          auto_activate: false,
          banner: "suggestion_only — evaluation cannot activate a strategy refinement",
        },
      ],
      narrative: {
        banner: "NARRATIVE_NOT_FACT — LLM wording cannot rewrite deterministic facts",
        text: "Narrative sibling only.",
      },
    },
  };
}

describe("PaperEvaluationSummaryCard", () => {
  afterEach(() => cleanup());

  it("renders measurement facts and labels refinements as not activated", () => {
    render(<PaperEvaluationSummaryCard evaluation={evaluation()} />);
    expect(screen.getByTestId("paper-evaluation-summary")).toHaveTextContent(
      /refinements are suggestions/i,
    );
    expect(screen.getByTestId("paper-evaluation-watcher")).toHaveTextContent("Scans: 3");
    expect(screen.getByTestId("paper-evaluation-performance")).toHaveTextContent("Win rate");
    expect(screen.getByTestId("paper-evaluation-performance")).toHaveTextContent("Wins: 1");
    expect(screen.getByTestId("paper-evaluation-performance")).toHaveTextContent("Losses: 0");
    expect(screen.getByTestId("paper-evaluation-performance")).toHaveTextContent("Net PnL: 10");
    expect(screen.getByTestId("paper-evaluation-setups")).toHaveTextContent("setup-1");
    expect(screen.getByTestId("paper-evaluation-setups")).toHaveTextContent("strategy-1");
    expect(screen.getByTestId("paper-evaluation-missed-warning")).toHaveTextContent(
      /counterfactual pnl is not invented/i,
    );
    expect(screen.getByTestId("paper-evaluation-narrative")).toHaveTextContent("NARRATIVE_NOT_FACT");
    expect(screen.getByTestId("paper-evaluation-refinements")).toHaveTextContent("Not activated");
    expect(screen.getByText("Watcher not activated")).toBeInTheDocument();
  });

  it("renders an unavailable state without claiming Watcher is running", () => {
    render(<PaperEvaluationSummaryCard evaluation={null} />);
    expect(screen.getByTestId("paper-evaluation-summary")).toHaveTextContent(
      /paper evaluation api unavailable/i,
    );
    expect(screen.queryByText("RUNNING")).not.toBeInTheDocument();
  });
});
