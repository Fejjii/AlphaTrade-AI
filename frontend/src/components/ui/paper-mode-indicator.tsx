"use client";

import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useSafetyPosture } from "@/contexts/AppContext";
import { cn } from "@/lib/utils";

export interface PaperModeIndicatorProps {
  /**
   * Explicit verified paper confirmation from runtime safety posture.
   * Defaults to unconfirmed (fail-closed). Never infer from build config.
   */
  active?: boolean;
  className?: string;
  compact?: boolean;
}

/** True only when execution_mode is paper and real trading is explicitly disabled. */
export function isPaperModeConfirmed(
  executionMode: string | null | undefined,
  realTradingEnabled: boolean | null | undefined,
): boolean {
  return executionMode === "paper" && realTradingEnabled === false;
}

/**
 * Compact persistent paper-mode chip for shell/header.
 * Fail-closed: defaults to unconfirmed; active paper only when caller passes true.
 */
export function PaperModeIndicator({
  active = false,
  className,
  compact = true,
}: PaperModeIndicatorProps) {
  if (!active) {
    return (
      <Badge
        variant="blocked"
        className={cn(className)}
        data-testid="paper-mode-indicator"
        aria-label="Paper mode not confirmed"
      >
        <FileText className="h-3 w-3" aria-hidden="true" />
        <span>{compact ? "Not paper" : "Paper mode not confirmed"}</span>
      </Badge>
    );
  }

  return (
    <Badge
      variant="paper"
      className={cn(className)}
      data-testid="paper-mode-indicator"
      aria-label="Paper mode active"
    >
      <FileText className="h-3 w-3" aria-hidden="true" />
      <span>{compact ? "Paper" : "Paper mode active"}</span>
    </Badge>
  );
}

/**
 * PaperModeIndicator wired to backend /health via useSafetyPosture (fail-closed).
 */
export function VerifiedPaperModeIndicator({
  className,
  compact = true,
}: {
  className?: string;
  compact?: boolean;
}) {
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  return (
    <PaperModeIndicator
      active={isPaperModeConfirmed(executionMode, realTradingEnabled)}
      className={className}
      compact={compact}
    />
  );
}
