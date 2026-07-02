"use client";

import { Badge } from "@/components/ui/badge";
import type { PaperPortfolioSafetyBanner as SafetyBanner } from "@/lib/api/types";

export function PaperPortfolioSafetyBanner({ safety }: { safety: SafetyBanner }) {
  return (
    <section
      className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4"
      data-testid="paper-portfolio-safety-banner"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="success" data-testid="paper-portfolio-paper-only">
          Paper-only simulated portfolio
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
