import { Lock } from "lucide-react";

import { cn } from "@/lib/utils";

export interface RiskBlockProps {
  reason: string;
  /** Rule reference shown to operators — never an override control */
  ruleReference?: string;
  className?: string;
}

/**
 * Risk engine BLOCK panel — final. No UI override control exists.
 * Color is paired with lock icon + explicit "BLOCKED" label.
 */
export function RiskBlock({ reason, ruleReference, className }: RiskBlockProps) {
  return (
    <div
      role="alert"
      data-testid="risk-block"
      className={cn(
        "rounded-card border border-blocked-border bg-blocked-muted px-4 py-4",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <Lock className="mt-0.5 h-5 w-5 shrink-0 text-blocked" aria-hidden="true" />
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-semibold uppercase tracking-wide text-blocked">Blocked</p>
          <p className="text-sm text-text-primary">{reason}</p>
          {ruleReference ? (
            <p className="text-caption text-text-muted">Rule: {ruleReference}</p>
          ) : null}
          <p className="text-caption text-text-secondary">
            The risk engine BLOCK is final. No override is available in the UI.
          </p>
        </div>
      </div>
    </div>
  );
}
