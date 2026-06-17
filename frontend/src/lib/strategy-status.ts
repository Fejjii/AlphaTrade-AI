/**
 * Derive a single trader-facing status badge and next action for a strategy.
 *
 * Maps the various raw status fields on a strategy into one calm, readable
 * badge so the Strategy Lab list and dashboard readiness card stay scannable.
 */

import type { UserStrategy } from "@/lib/api/types";

export type StrategyBadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "muted";

export interface StrategyStatusView {
  label: string;
  variant: StrategyBadgeVariant;
  nextAction: string;
}

const COMPLETED_BACKTEST = new Set(["completed", "complete", "passed", "succeeded"]);

/** Minimal shape so callers can pass a full strategy or a lightweight summary. */
export interface StrategyStatusInput {
  validation_status?: string | null;
  backtest_status?: string | null;
  paper_validation_status?: string | null;
  paper_eligible?: boolean;
}

export function strategyStatusView(strategy: StrategyStatusInput): StrategyStatusView {
  const validation = (strategy.validation_status ?? "draft").toLowerCase();
  const backtest = (strategy.backtest_status ?? "not_run").toLowerCase();
  const paper = (strategy.paper_validation_status ?? "not_started").toLowerCase();

  if (paper === "restricted" || paper === "blocked") {
    return {
      label: "Restricted",
      variant: "danger",
      nextAction: "Review blockers before retrying paper validation.",
    };
  }
  if (paper === "validated" || paper === "complete" || paper === "completed") {
    return {
      label: "Paper validated",
      variant: "success",
      nextAction: "Review results and fold lessons into the next version.",
    };
  }
  if (paper === "running" || paper === "active" || paper === "in_progress") {
    return {
      label: "Paper validation running",
      variant: "info",
      nextAction: "Review latest scans and simulated trades.",
    };
  }
  if (strategy.paper_eligible) {
    return {
      label: "Paper eligible",
      variant: "success",
      nextAction: "Start paper validation to simulate this strategy.",
    };
  }
  if (COMPLETED_BACKTEST.has(backtest)) {
    return {
      label: "Needs more sample",
      variant: "warning",
      nextAction: "Gather a larger backtest sample to unlock paper validation.",
    };
  }
  if (backtest === "running") {
    return {
      label: "Backtest running",
      variant: "info",
      nextAction: "Backtest in progress — check back shortly.",
    };
  }
  if (validation === "draft" || validation === "needs_structure") {
    return {
      label: "Needs structure",
      variant: "muted",
      nextAction: "Add structured rules so the strategy can be backtested.",
    };
  }
  return {
    label: "Ready for backtest",
    variant: "default",
    nextAction: "Run a backtest to gather a performance sample.",
  };
}

/** Convenience for callers that already hold a full strategy. */
export function strategyStatusFor(strategy: UserStrategy): StrategyStatusView {
  return strategyStatusView(strategy);
}
