"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { PaperApprovalPanel } from "@/components/canonical-decision/PaperApprovalPanel";
import { TradePlanView } from "@/components/canonical-decision/TradePlanView";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { tradePlanFromProposal } from "@/lib/canonical-decision/trade-plan";

export default function DecisionApprovalPage() {
  const params = useParams<{ approvalId: string }>();
  const approvalId = params.approvalId;
  const [busy, setBusy] = useState(false);
  const loader = useCallback(() => api.approvals.workflow(approvalId), [approvalId]);
  const { data, loading, error, reload } = useAsyncData(loader, [approvalId]);
  const plan = useMemo(
    () => (data?.proposal ? tradePlanFromProposal(data.proposal) : null),
    [data],
  );

  async function run(action: (id: string) => Promise<unknown>) {
    setBusy(true);
    try {
      await action(approvalId);
      await reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <DecisionChrome
      title="Paper approval"
      description="Human authorization only. Approval does not execute, and AI cannot bypass this step."
      current="approval"
    >
      {loading ? <LoadingState label="Loading approval…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {data ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {plan ? <TradePlanView plan={plan} /> : null}
          <PaperApprovalPanel
            approval={data.approval}
            proposal={data.proposal}
            busy={busy}
            onApprove={(id) => void run(() => api.approvals.approve(id, "Approved in decision workflow"))}
            onReject={(id) => void run(() => api.approvals.reject(id, "Rejected in decision workflow"))}
            onRefresh={() => void reload()}
          />
        </div>
      ) : null}
    </DecisionChrome>
  );
}
