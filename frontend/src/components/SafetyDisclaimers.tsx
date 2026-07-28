"use client";

import { useSafetyPosture } from "@/contexts/AppContext";
import { isPaperModeConfirmed } from "@/components/ui/paper-mode-indicator";

/**
 * Shared, consistent safety disclaimers used across trader-facing pages.
 * Wording is intentionally calm and non-judgmental.
 *
 * Runtime posture claims ("paper only", "real trading disabled") are gated on
 * verified backend /health posture (FP2-104) — they are never asserted from
 * build configuration alone.
 */

/** Always true regardless of runtime posture. */
export const UNIVERSAL_DISCLAIMERS = [
  "Not financial advice.",
  "Alerts do not execute trades.",
  "Paper validation trades are simulated, not real orders.",
  "AI explanations never override deterministic risk rules.",
] as const;

/** Asserted only when backend /health confirms paper-only posture. */
export const VERIFIED_PAPER_DISCLAIMERS = [
  "Paper trading only — no real orders are placed.",
  "Real trading is disabled.",
] as const;

export function SafetyDisclaimers({ className }: { className?: string }) {
  const { executionMode, realTradingEnabled, postureKnown } = useSafetyPosture();
  const paperConfirmed = postureKnown && isPaperModeConfirmed(executionMode, realTradingEnabled);

  const postureLines = paperConfirmed
    ? [...VERIFIED_PAPER_DISCLAIMERS]
    : [
        postureKnown
          ? "Runtime posture is not confirmed as paper-only — verify the deployment configuration."
          : "Runtime trading posture unverified — paper-only execution is confirmed from backend health, never assumed.",
      ];

  return (
    <ul
      className={`space-y-1 text-xs text-zinc-500 ${className ?? ""}`}
      data-testid="safety-disclaimers"
    >
      {[...postureLines, ...UNIVERSAL_DISCLAIMERS].map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}
