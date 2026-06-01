"use client";

import { useCallback } from "react";

import { AuditEventCard } from "@/components/AuditEventCard";
import { ApprovalCard } from "@/components/ApprovalCard";
import { PositionCard } from "@/components/PositionCard";
import { ProviderStatusCard } from "@/components/ProviderStatusCard";
import { TradeProposalCard } from "@/components/TradeProposalCard";
import { UsageMetricCard } from "@/components/UsageMetricCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAppContext } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { formatDecimal } from "@/lib/utils";

export default function DashboardPage() {
  const { providers, health } = useAppContext();
  const loader = useCallback(async () => {
    const [proposals, approvals, positions, usage, audit] = await Promise.all([
      api.proposals.list({ limit: 5 }),
      api.approvals.list({ limit: 5, status: "pending" }),
      api.positions.list({ limit: 5, status: "open" }),
      api.usage.summary(),
      api.audit.events({ limit: 5 }),
    ]);
    return { proposals, approvals, positions, usage, audit };
  }, []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-50">Dashboard</h1>
        <p className="text-sm text-zinc-400">
          Paper-only overview of proposals, approvals, positions, usage, and audit activity.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <UsageMetricCard label="Backend version" value={health?.version ?? "—"} />
        <UsageMetricCard label="Usage events" value={data?.usage.event_count ?? 0} />
        <UsageMetricCard
          label="Estimated cost"
          value={formatDecimal(data?.usage.total_estimated_cost)}
          hint={data?.usage.cost_is_placeholder ? "Placeholder estimate — not billing grade" : undefined}
        />
        <UsageMetricCard label="Open positions" value={data?.positions.total ?? 0} />
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-medium text-zinc-100">Provider status</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(providers?.providers ?? []).slice(0, 6).map((provider) => (
            <ProviderStatusCard key={provider.name} provider={provider} />
          ))}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="space-y-3">
          <h2 className="text-lg font-medium">Open proposals</h2>
          {data?.proposals.items.length ? (
            data.proposals.items.map((proposal) => (
              <TradeProposalCard key={proposal.id} proposal={proposal} />
            ))
          ) : (
            <EmptyState title="No proposals yet" description="Agent or manual flows will appear here." />
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-medium">Pending approvals</h2>
          {data?.approvals.items.length ? (
            data.approvals.items.map((approval) => (
              <ApprovalCard key={approval.id} approval={approval} />
            ))
          ) : (
            <EmptyState title="No pending approvals" />
          )}
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="space-y-3">
          <h2 className="text-lg font-medium">Open positions</h2>
          {data?.positions.items.length ? (
            data.positions.items.map((position) => (
              <PositionCard key={position.id} position={position} />
            ))
          ) : (
            <EmptyState title="No open paper positions" />
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-medium">Recent audit events</h2>
          {data?.audit.items.length ? (
            data.audit.items.map((event) => <AuditEventCard key={event.event_id} event={event} />)
          ) : (
            <EmptyState title="No audit events yet" />
          )}
        </section>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Risk summary</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-400">
          Deterministic risk engine results appear on proposals and in the AI workspace. Risk blocks
          are final unless future settings explicitly allow overrides.
        </CardContent>
      </Card>
    </div>
  );
}
