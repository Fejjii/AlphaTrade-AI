import type { QuotaStatus } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function pctLabel(value: number): string {
  return `${Math.round(value * 100)}%`;
}

type QuotaPanelProps = {
  quota: QuotaStatus;
  /** ISO currency from a plan when the backend provides one — never invent `$`. */
  currencyCode?: string | null;
};

export function QuotaPanel({ quota, currencyCode = null }: QuotaPanelProps) {
  const { usage, warnings, soft_limit_reached, hard_limit_reached } = quota;

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-medium">Quota</h2>
      {soft_limit_reached ? (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="p-4 text-sm text-amber-100">
            {warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </CardContent>
        </Card>
      ) : null}
      {hard_limit_reached ? (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="p-4 text-sm text-red-100">
            Hard quota limit reached — some features may be blocked.
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Monthly tokens</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-zinc-300">
            {usage.monthly_tokens_used.toLocaleString()} /{" "}
            {usage.monthly_tokens_limit.toLocaleString()} ({pctLabel(usage.monthly_tokens_pct)})
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Monthly cost (est.)</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-zinc-300" data-testid="quota-monthly-cost">
            {formatCurrency(usage.monthly_cost_used, currencyCode)} /{" "}
            {formatCurrency(usage.monthly_cost_limit, currencyCode)} (
            {pctLabel(usage.monthly_cost_pct)})
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Daily requests</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-zinc-300">
            {usage.daily_requests_used} / {usage.daily_requests_limit} (
            {pctLabel(usage.daily_requests_pct)})
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
