"use client";

import { useCallback } from "react";

import { CostSourceBadge } from "@/components/usage/CostSourceBadge";
import { QuotaPanel } from "@/components/usage/QuotaPanel";
import { UsageFeatureTable, UsageProviderTable } from "@/components/usage/UsageProviderTable";
import { UsageMetricCard } from "@/components/UsageMetricCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { formatDate, formatDecimal } from "@/lib/utils";

export default function UsagePage() {
  const loader = useCallback(async () => {
    const [summary, events, quota, byFeature, byProvider] = await Promise.all([
      api.usage.summary(),
      api.usage.events({ limit: 20 }),
      api.usage.quota(),
      api.usage.byFeature(),
      api.usage.byProvider(),
    ]);
    return { summary, events, quota, byFeature, byProvider };
  }, []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Usage</h1>
        <p className="text-sm text-zinc-400">
          Organization token usage, cost estimates, and quota limits.
        </p>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        <>
          <CostSourceBadge summary={data.summary} />
          <QuotaPanel quota={data.quota} />
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <UsageMetricCard label="Events" value={data.summary.event_count} />
            <UsageMetricCard label="Monthly tokens" value={data.summary.total_tokens} />
            <UsageMetricCard
              label="Est. monthly cost"
              value={formatDecimal(data.summary.total_cost)}
            />
            <UsageMetricCard label="Fallback count" value={data.summary.fallback_count} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <UsageFeatureTable rows={data.byFeature} />
            <UsageProviderTable rows={data.byProvider} />
          </div>
          <section className="space-y-3">
            <h2 className="text-lg font-medium">Recent usage events</h2>
            {data.events.items.length ? (
              data.events.items.map((event) => (
                <Card key={`${event.request_id}-${event.timestamp}`}>
                  <CardHeader>
                    <CardTitle className="text-sm">
                      {event.feature} · {event.provider ?? "unknown"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-sm text-zinc-400">
                    {event.total_tokens} tokens · {event.cost_source} ·{" "}
                    {formatDecimal(event.estimated_cost)} est. · {formatDate(event.timestamp)}
                    {event.fallback_used ? " · fallback" : ""}
                  </CardContent>
                </Card>
              ))
            ) : (
              <EmptyState title="No usage events" />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
