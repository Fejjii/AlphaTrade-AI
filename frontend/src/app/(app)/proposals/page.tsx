"use client";

import { Suspense, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { ProposalDetailPanel } from "@/components/ProposalDetailPanel";
import { TradeProposalCard } from "@/components/TradeProposalCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

function ProposalsContent() {
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("id");
  const loader = useCallback(() => api.proposals.list({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  const selected = useMemo(
    () => data?.items.find((item) => item.id === selectedId) ?? data?.items[0],
    [data, selectedId],
  );

  const workflowLoader = useCallback(
    () => (selected ? api.proposals.workflow(selected.id) : Promise.resolve(null)),
    [selected],
  );
  const workflow = useAsyncData(workflowLoader, [selected?.id]);

  if (loading) return <LoadingState label="Loading proposals…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <section className="space-y-3">
        {data?.items.length ? (
          data.items.map((proposal) => <TradeProposalCard key={proposal.id} proposal={proposal} />)
        ) : (
          <EmptyState
            title="No trade proposals"
            description="Run the AI workspace or create proposals via API to review plans here."
          />
        )}
      </section>

      {selected ? (
        workflow.loading ? (
          <LoadingState label="Loading proposal workflow…" />
        ) : workflow.error ? (
          <ErrorState message={workflow.error} onRetry={() => void workflow.reload()} />
        ) : (
          <ProposalDetailPanel
            proposal={workflow.data?.proposal ?? selected}
            approval={workflow.data?.approval}
            onRefresh={() => {
              void reload();
              void workflow.reload();
            }}
          />
        )
      ) : (
        <EmptyState title="Select a proposal" description="Choose a proposal to review details." />
      )}
    </div>
  );
}

export default function ProposalsPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Trade Proposals</h1>
          <p className="text-sm text-zinc-400">Review structured plans with exits and risk results.</p>
        </div>
        <KillSwitchButton compact />
      </div>
      <Suspense fallback={<LoadingState label="Loading proposals…" />}>
        <ProposalsContent />
      </Suspense>
    </div>
  );
}
