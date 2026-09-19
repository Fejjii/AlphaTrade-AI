import {
  DECISION_STAGES,
  type DecisionStage,
} from "@/lib/canonical-decision/types";

export type StepStatus = "complete" | "current" | "upcoming" | "blocked";

export interface DecisionStep {
  key: DecisionStage;
  label: string;
  shortLabel: string;
  href: string;
  status: StepStatus;
  description: string;
}

const STEP_META: Record<
  DecisionStage,
  { label: string; shortLabel: string; href: string; description: string }
> = {
  market_assessment: {
    label: "Market assessment",
    shortLabel: "Market",
    href: "/decision/market",
    description: "Market quality, evidence freshness, and setup confidence — not permission to trade.",
  },
  candidate: {
    label: "Candidate",
    shortLabel: "Candidate",
    href: "/decision/candidates",
    description: "Setup, evidence, and confidence for a candidate workspace.",
  },
  eligibility: {
    label: "Action eligibility",
    shortLabel: "Eligibility",
    href: "/decision/candidates",
    description: "Account, risk, kill switch, and configuration gates. Independent of market quality.",
  },
  trade_plan: {
    label: "TradePlan",
    shortLabel: "Plan",
    href: "/decision",
    description: "Entry, stop, target, sizing, risk, and lineage for a paper plan.",
  },
  approval: {
    label: "Human approval",
    shortLabel: "Approve",
    href: "/decision",
    description: "Human authorization only. AI recommendation cannot approve or execute.",
  },
  paper_execution: {
    label: "Paper execution",
    shortLabel: "Paper",
    href: "/decision",
    description: "Simulated paper order status. Live execution is not available.",
  },
  outcome: {
    label: "Outcome",
    shortLabel: "Outcome",
    href: "/journal",
    description: "Journaled result linked to the approved paper plan.",
  },
  learning: {
    label: "Learning",
    shortLabel: "Learn",
    href: "/decision/strategy",
    description: "Lessons and pattern performance. No automatic strategy promotion.",
  },
};

const STAGE_INDEX: Record<DecisionStage, number> = Object.fromEntries(
  DECISION_STAGES.map((stage, index) => [stage, index]),
) as Record<DecisionStage, number>;

export function stageIndex(stage: DecisionStage): number {
  return STAGE_INDEX[stage];
}

/**
 * Build the eight-step spine. `current` is the case stage; earlier steps are
 * complete, later steps upcoming. Eligibility can be blocked without moving
 * market quality backward.
 */
export function buildDecisionSteps(input: {
  current: DecisionStage;
  eligibilityBlocked?: boolean;
  killSwitchActive?: boolean;
}): DecisionStep[] {
  const currentIndex = stageIndex(input.current);
  return DECISION_STAGES.map((key, index) => {
    const meta = STEP_META[key];
    let status: StepStatus;
    if (index < currentIndex) {
      status = "complete";
    } else if (index === currentIndex) {
      status = input.eligibilityBlocked && key === "eligibility" ? "blocked" : "current";
    } else if (
      (input.killSwitchActive || input.eligibilityBlocked) &&
      (key === "trade_plan" || key === "approval" || key === "paper_execution")
    ) {
      status = "blocked";
    } else {
      status = "upcoming";
    }
    return { key, status, ...meta };
  });
}

export function stageLabel(stage: DecisionStage): string {
  return STEP_META[stage].label;
}
