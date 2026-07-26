import { isPaperModeConfirmed } from "@/components/ui/paper-mode-indicator";

export type SafetyPostureKind =
  | "confirmed_paper"
  | "safety_conflict"
  | "execution_unverified"
  | "paper_not_confirmed"
  | "non_paper_mode";

export type SafetyPostureDisplay = {
  kind: SafetyPostureKind;
  paperConfirmed: boolean;
  executionLabel: string;
  executionVariant: "success" | "warning" | "danger" | "muted";
  realTradingLabel: string;
  realTradingVariant: "success" | "warning" | "danger" | "muted";
  runtimeBadgeLabel: string;
  runtimeBadgeVariant: "paper" | "muted" | "danger" | "warning";
  conflictMessage: string | null;
};

/**
 * Honest runtime safety wording derived only from verified posture fields.
 * Confirmed PAPER requires executionMode === "paper" AND realTradingEnabled === false.
 */
export function describeSafetyPosture(
  executionMode: string | null | undefined,
  realTradingEnabled: boolean | null | undefined,
): SafetyPostureDisplay {
  const paperConfirmed = isPaperModeConfirmed(executionMode, realTradingEnabled);
  const mode = executionMode ?? null;
  const real = realTradingEnabled ?? null;

  if (paperConfirmed) {
    return {
      kind: "confirmed_paper",
      paperConfirmed: true,
      executionLabel: "PAPER mode",
      executionVariant: "success",
      realTradingLabel: "Real trading disabled",
      realTradingVariant: "success",
      runtimeBadgeLabel: "Paper only",
      runtimeBadgeVariant: "paper",
      conflictMessage: null,
    };
  }

  if (real === true) {
    return {
      kind: "safety_conflict",
      paperConfirmed: false,
      executionLabel: mode ? `${mode.toUpperCase()} mode` : "Execution unverified",
      executionVariant: mode === "paper" ? "warning" : "danger",
      realTradingLabel: "Real trading enabled",
      realTradingVariant: "danger",
      runtimeBadgeLabel: "Safety conflict",
      runtimeBadgeVariant: "danger",
      conflictMessage:
        "Safety conflict: real trading is enabled. Paper-only workflow wording is suppressed.",
    };
  }

  if (mode == null || real == null) {
    const partial = mode != null || real != null;
    return {
      kind: partial ? "paper_not_confirmed" : "execution_unverified",
      paperConfirmed: false,
      executionLabel: mode ? `${mode.toUpperCase()} mode` : "Execution unverified",
      executionVariant: "warning",
      realTradingLabel:
        real === false ? "Real trading disabled" : "Real trading unverified",
      realTradingVariant: real === false ? "success" : "warning",
      runtimeBadgeLabel: partial ? "Paper mode not confirmed" : "Runtime posture unverified",
      runtimeBadgeVariant: "warning",
      conflictMessage: null,
    };
  }

  return {
    kind: "non_paper_mode",
    paperConfirmed: false,
    executionLabel: `${mode.toUpperCase()} mode`,
    executionVariant: "warning",
    realTradingLabel: "Real trading disabled",
    realTradingVariant: "success",
    runtimeBadgeLabel: `${mode} mode`,
    runtimeBadgeVariant: "muted",
    conflictMessage: null,
  };
}
