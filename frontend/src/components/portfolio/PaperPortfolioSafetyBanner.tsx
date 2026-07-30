"use client";

import { Badge } from "@/components/ui/badge";
import type { PaperPortfolioSafetyBanner as SafetyBanner } from "@/lib/api/types";

/**
 * Portfolio safety banner for non-redundant honesty only (FP2-123).
 *
 * When the payload confirms paper-only with real trading disabled, the global
 * StatusStrip plus page-header PaperModeIndicator already communicate verified
 * paper posture — suppress this third surface to stay at ≤2 posture chrome layers.
 * Unverified or degraded safety states always remain visible.
 */
export function PaperPortfolioSafetyBanner({ safety }: { safety: SafetyBanner }) {
  const verifiedPaperSafe = safety.paper_only === true && safety.real_trading_enabled === false;
  if (verifiedPaperSafe) {
    return null;
  }

  return (
    <section
      className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4"
      data-testid="paper-portfolio-safety-banner"
      role="alert"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant={safety.paper_only ? "success" : "danger"}
          data-testid="paper-portfolio-paper-only"
        >
          {safety.paper_only ? "Paper-only simulated portfolio" : "Paper-only not confirmed"}
        </Badge>
        <Badge variant="muted">Not live trading</Badge>
        <Badge variant={safety.real_trading_enabled ? "danger" : "success"}>
          Real trading {safety.real_trading_enabled ? "enabled" : "disabled"}
        </Badge>
      </div>
      <p className="mt-3 text-sm text-zinc-300">{safety.disclaimer}</p>
      <p className="mt-2 text-xs text-zinc-500">
        Not investment advice. Does not indicate readiness for real money.
      </p>
    </section>
  );
}
