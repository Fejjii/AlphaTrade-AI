"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { pnlClassName } from "@/components/portfolio/portfolio-display";
import type { OpenExposureSummary } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

export function OpenExposurePanel({ exposure }: { exposure: OpenExposureSummary }) {
  return (
    <Card data-testid="paper-portfolio-open-exposure">
      <CardHeader>
        <CardTitle className="text-base">Open exposure</CardTitle>
        <p className="text-xs text-zinc-500">
          Read-only view of open simulated positions — no orders or automation.
        </p>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="text-xs text-zinc-500">Open trades</p>
          <p className="text-lg font-semibold text-zinc-100">{exposure.open_trade_count}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Proposal flow</p>
          <p className="text-lg font-semibold text-zinc-100">{exposure.proposal_flow_count}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Paper validation</p>
          <p className="text-lg font-semibold text-zinc-100">{exposure.paper_validation_count}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Unrealized PnL total</p>
          <p className={`text-lg font-semibold ${pnlClassName(exposure.unrealized_pnl_total)}`}>
            {exposure.unrealized_pnl_total != null
              ? formatDecimal(exposure.unrealized_pnl_total)
              : "Partial / unavailable"}
          </p>
        </div>
        {exposure.notional_exposure != null ? (
          <div>
            <p className="text-xs text-zinc-500">Notional exposure</p>
            <p className="text-lg font-semibold text-zinc-100">
              {formatDecimal(exposure.notional_exposure)}
            </p>
          </div>
        ) : null}
        {exposure.limitations.length ? (
          <div className="sm:col-span-2 lg:col-span-4">
            <p className="text-xs font-medium text-amber-500/90">Limitations</p>
            <ul className="mt-1 space-y-1 text-xs text-amber-500/80">
              {exposure.limitations.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
