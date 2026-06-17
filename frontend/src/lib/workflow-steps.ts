/**
 * Trader workflow stepper model.
 *
 * Describes the end-to-end paper-only flow a trader follows:
 *   Idea → Structure → Backtest → Paper Validate → Review Lessons → Improve Strategy
 *
 * Status is derived deterministically from whatever strategy signals are
 * available, so the same helper works on the dashboard (strategy summary
 * fields only) and on the strategy detail page (testability + eligibility).
 */

export type WorkflowStepStatus = "complete" | "current" | "blocked" | "upcoming";

export type WorkflowStepKey =
  | "idea"
  | "structure"
  | "backtest"
  | "paper_validate"
  | "review_lessons"
  | "improve_strategy";

export interface WorkflowStep {
  key: WorkflowStepKey;
  label: string;
  status: WorkflowStepStatus;
  /** Short, calm guidance for what to do at this step. */
  nextAction: string;
  /** Relative app link to the most relevant page for this step. */
  href: string;
}

/** Normalised inputs; all optional so callers can pass partial data. */
export interface WorkflowInput {
  strategyId?: string | null;
  hasStructuredRules?: boolean;
  readyForBacktest?: boolean;
  backtestStatus?: string | null;
  paperValidationStatus?: string | null;
  paperEligible?: boolean;
  unresolvedLessonCount?: number;
}

const COMPLETED_BACKTEST = new Set(["completed", "complete", "passed", "succeeded"]);
const ACTIVE_PAPER = new Set(["running", "active", "in_progress"]);
const DONE_PAPER = new Set(["validated", "complete", "completed", "passed"]);
const RESTRICTED_PAPER = new Set(["restricted", "blocked"]);

function strategyHref(strategyId?: string | null): string {
  return strategyId ? `/strategy-lab/${strategyId}` : "/strategy-lab";
}

/**
 * Build the ordered workflow steps for a strategy.
 *
 * Each step is at most one of: complete, current, blocked, upcoming. The first
 * non-complete actionable step (current or blocked) is what the trader should
 * focus on next.
 */
export function buildWorkflowSteps(input: WorkflowInput): WorkflowStep[] {
  const href = strategyHref(input.strategyId);
  const backtestStatus = (input.backtestStatus ?? "not_run").toLowerCase();
  const paperStatus = (input.paperValidationStatus ?? "not_started").toLowerCase();

  const structureDone = Boolean(
    input.hasStructuredRules ||
      input.readyForBacktest ||
      (backtestStatus !== "not_run" && backtestStatus !== "not_started"),
  );
  const backtestDone = COMPLETED_BACKTEST.has(backtestStatus);
  const backtestRunning = backtestStatus === "running";
  const paperRestricted = RESTRICTED_PAPER.has(paperStatus);
  const paperActive = ACTIVE_PAPER.has(paperStatus);
  const paperDone = DONE_PAPER.has(paperStatus);
  const unresolved = input.unresolvedLessonCount ?? 0;

  const structure: WorkflowStep = {
    key: "structure",
    label: "Structure",
    status: structureDone ? "complete" : "current",
    nextAction: structureDone
      ? "Structured rules are in place."
      : "Add structured entry, exit, and no-trade rules.",
    href,
  };

  let backtest: WorkflowStep;
  if (!structureDone) {
    backtest = {
      key: "backtest",
      label: "Backtest",
      status: "blocked",
      nextAction: "Finish structuring the strategy first.",
      href,
    };
  } else if (backtestDone) {
    backtest = { key: "backtest", label: "Backtest", status: "complete", nextAction: "Backtest complete.", href };
  } else if (backtestRunning) {
    backtest = { key: "backtest", label: "Backtest", status: "current", nextAction: "Backtest is running.", href };
  } else {
    backtest = {
      key: "backtest",
      label: "Backtest",
      status: "current",
      nextAction: "Run a backtest to gather a sample.",
      href,
    };
  }

  let paperValidate: WorkflowStep;
  if (paperRestricted) {
    paperValidate = {
      key: "paper_validate",
      label: "Paper Validate",
      status: "blocked",
      nextAction: "Paper validation is restricted — review blockers.",
      href,
    };
  } else if (!backtestDone) {
    paperValidate = {
      key: "paper_validate",
      label: "Paper Validate",
      status: "blocked",
      nextAction: "Complete a backtest before paper validation.",
      href,
    };
  } else if (!input.paperEligible) {
    paperValidate = {
      key: "paper_validate",
      label: "Paper Validate",
      status: "blocked",
      nextAction: "Resolve eligibility blockers to unlock paper validation.",
      href,
    };
  } else if (paperDone) {
    paperValidate = {
      key: "paper_validate",
      label: "Paper Validate",
      status: "complete",
      nextAction: "Paper validation finished.",
      href,
    };
  } else if (paperActive) {
    paperValidate = {
      key: "paper_validate",
      label: "Paper Validate",
      status: "current",
      nextAction: "Paper validation is running — review scans and trades.",
      href,
    };
  } else {
    paperValidate = {
      key: "paper_validate",
      label: "Paper Validate",
      status: "current",
      nextAction: "Start paper validation to simulate this strategy.",
      href,
    };
  }

  const reviewLessons: WorkflowStep = {
    key: "review_lessons",
    label: "Review Lessons",
    status: unresolved > 0 ? "current" : paperActive || paperDone ? "complete" : "upcoming",
    nextAction:
      unresolved > 0
        ? `${unresolved} learning signal${unresolved === 1 ? "" : "s"} waiting for review.`
        : "No learning signals pending review.",
    href: "/lessons",
  };

  const priorComplete =
    structure.status === "complete" &&
    backtest.status === "complete" &&
    (paperValidate.status === "complete" || paperValidate.status === "current") &&
    reviewLessons.status !== "current";

  const improveStrategy: WorkflowStep = {
    key: "improve_strategy",
    label: "Improve Strategy",
    status: priorComplete ? "current" : "upcoming",
    nextAction: priorComplete
      ? "Fold accepted lessons into a new strategy version."
      : "Available after a validation cycle completes.",
    href,
  };

  const idea: WorkflowStep = {
    key: "idea",
    label: "Idea",
    status: "complete",
    nextAction: "Strategy created.",
    href,
  };

  return [idea, structure, backtest, paperValidate, reviewLessons, improveStrategy];
}

/** The step the trader should focus on next, if any. */
export function firstActionableStep(steps: WorkflowStep[]): WorkflowStep | null {
  return steps.find((s) => s.status === "current") ?? steps.find((s) => s.status === "blocked") ?? null;
}
