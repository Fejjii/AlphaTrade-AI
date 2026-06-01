"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApprovalCard } from "@/components/ApprovalCard";
import { ApprovalDetailPanel } from "@/components/ApprovalDetailPanel";
import { KillSwitchButton } from "@/components/KillSwitchButton";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

function ApprovalsContent() {
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("id");
  const [busy, setBusy] = useState(false);
  const loader = useCallback(() => api.approvals.list({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  const selected = useMemo(
    () => data?.items.find((item) => item.id === selectedId) ?? data?.items[0],
    [data, selectedId],
  );

  const workflowLoader = useCallback(
    () => (selected ? api.approvals.workflow(selected.id) : Promise.resolve(null)),
    [selected],
  );
  const workflow = useAsyncData(workflowLoader, [selected?.id]);

  async function runAction(action: (id: string) => Promise<unknown>, id: string) {
    setBusy(true);
    try {
      await action(id);
      await reload();
      await workflow.reload();
    } finally {
      setBusy(false);
    }
  }

  async function runModify(id: string, fields: Record<string, string>, reason?: string) {
    setBusy(true);
    try {
      await api.approvals.modify(id, reason, fields);
      await reload();
      await workflow.reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {loading ? <LoadingState label="Loading approvals…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="grid gap-4">
          {data?.items.length ? (
            data.items.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                busy={busy}
                onApprove={(id) => runAction((value) => api.approvals.approve(value, "Approved in UI"), id)}
                onReject={(id) => runAction((value) => api.approvals.reject(value, "Rejected in UI"), id)}
                onNeedsAnalysis={(id) =>
                  runAction((value) => api.approvals.needsMoreAnalysis(value, "Needs review"), id)
                }
              />
            ))
          ) : (
            <EmptyState
              title="No approval requests"
              description="Proposals requiring human review will appear here."
            />
          )}
        </section>

        {selected ? (
          workflow.loading ? (
            <LoadingState label="Loading approval workflow…" />
          ) : workflow.error ? (
            <ErrorState message={workflow.error} onRetry={() => void workflow.reload()} />
          ) : (
            <ApprovalDetailPanel
              approval={workflow.data?.approval ?? selected}
              proposal={workflow.data?.proposal}
              busy={busy}
              onApprove={(id) => runAction((value) => api.approvals.approve(value, "Approved in UI"), id)}
              onReject={(id) => runAction((value) => api.approvals.reject(value, "Rejected in UI"), id)}
              onNeedsAnalysis={(id) =>
                runAction((value) => api.approvals.needsMoreAnalysis(value, "Needs review"), id)
              }
              onModify={runModify}
              onRefresh={() => {
                void reload();
                void workflow.reload();
              }}
            />
          )
        ) : (
          <EmptyState title="Select an approval" description="Choose an approval to review details." />
        )}
      </div>
    </>
  );
}

export default function ApprovalsPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Approvals</h1>
          <p className="text-sm text-zinc-400">
            Human-in-the-loop decisions gate paper execution. Real trading remains disabled.
          </p>
        </div>
        <KillSwitchButton compact />
      </div>

      <Suspense fallback={<LoadingState label="Loading approvals…" />}>
        <ApprovalsContent />
      </Suspense>
    </div>
  );
}
