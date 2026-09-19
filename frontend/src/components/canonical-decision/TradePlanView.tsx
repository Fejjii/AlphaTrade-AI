import Link from "next/link";

import { RiskBadge } from "@/components/RiskBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataNumber } from "@/components/ui/data-number";
import { RiskBlock } from "@/components/ui/risk-block";
import type { TradePlanViewModel } from "@/lib/canonical-decision/types";

export function TradePlanView({ plan }: { plan: TradePlanViewModel }) {
  return (
    <Card data-testid="trade-plan-view">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {plan.symbol} · {plan.direction.toUpperCase()}
          </CardTitle>
          <StatusBadge
            label={plan.authority === "canonical" ? "TradePlan revision" : "Legacy proposal"}
            tone={plan.authority === "canonical" ? "success" : "warn"}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {plan.riskAction === "block" ? (
          <RiskBlock
            reason={plan.riskSummary ?? "Risk engine BLOCK on this plan."}
            ruleReference="risk_engine"
          />
        ) : (
          <RiskBadge level={plan.riskAction === "warn" ? "medium" : "low"} />
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label="Entry" value={plan.entry} />
          <Metric label="Stop" value={plan.stop} />
          <Metric label="Size" value={plan.size} />
          <Metric label="Leverage" value={plan.leverage} />
          <Metric label="Risk budget" value={plan.riskBudget} />
          <Metric label="Max loss" value={plan.maximumLoss} />
        </div>
        <div>
          <h3 className="text-caption uppercase tracking-wide text-text-muted">Targets</h3>
          <ul className="mt-2 space-y-1">
            {plan.targets.map((target) => (
              <li key={target.label} className="flex justify-between gap-3">
                <span>{target.label}</span>
                <span className="font-data">
                  {target.price ?? "—"}
                  {target.fraction ? ` · ${target.fraction}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
        {plan.rationale ? <p className="text-text-secondary">{plan.rationale}</p> : null}
        <div>
          <h3 className="text-caption uppercase tracking-wide text-text-muted">Lineage</h3>
          <ul className="mt-2 space-y-1">
            {plan.lineage.map((item) => (
              <li key={`${item.label}-${item.value}`} className="flex flex-wrap gap-2">
                <span className="text-text-muted">{item.label}:</span>
                {item.href ? (
                  <Link href={item.href} className="text-accent underline">
                    {item.value}
                  </Link>
                ) : (
                  <span className="font-data break-all">{item.value}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
        {plan.approvalRequired ? (
          <p className="text-caption text-warning" data-testid="trade-plan-approval-required">
            Human approval is required before any paper order. AI cannot approve this plan.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-control bg-surface-0 p-3">
      <p className="text-caption text-text-muted">{label}</p>
      <DataNumber value={value ?? "—"} className="text-base text-text-primary" />
    </div>
  );
}
