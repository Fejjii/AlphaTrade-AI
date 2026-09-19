"use client";

import { useCallback, useMemo } from "react";
import { useParams } from "next/navigation";

import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { ExecutionLifecycle } from "@/components/canonical-decision/ExecutionLifecycle";
import { OutcomeLearning } from "@/components/canonical-decision/OutcomeLearning";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { loadSource } from "@/components/workflows";
import { executionFromOrder, executionFromReceipt } from "@/lib/canonical-decision/trade-plan";

export default function DecisionExecutionPage() {
  const params = useParams<{ executionId: string }>();
  const executionId = params.executionId;

  const loader = useCallback(async () => {
    const receipt = await loadSource(api.canonical.getExecutionReceipt(executionId));
    if (receipt.data) {
      return { kind: "canonical" as const, receipt: receipt.data };
    }
    const order = await api.execution.getOrder(executionId);
    const [proposal, approval, journals, lessons] = await Promise.all([
      order.proposal_id ? api.proposals.get(order.proposal_id) : Promise.resolve(null),
      order.approval_id ? api.approvals.get(order.approval_id) : Promise.resolve(null),
      api.journal.list({ limit: 50 }),
      api.lessons.listCandidates(),
    ]);
    return { kind: "compatibility" as const, order, proposal, approval, journals, lessons };
  }, [executionId]);

  const { data, loading, error, reload } = useAsyncData(loader, [executionId]);
  const execution = useMemo(() => {
    if (!data) return null;
    if (data.kind === "canonical") return executionFromReceipt(data.receipt);
    return executionFromOrder(data.order, data.proposal, data.approval, null);
  }, [data]);
  const outcome =
    data?.kind === "compatibility"
      ? data.journals.items.find((item) => item.linked_proposal_id === data.order.proposal_id)
      : undefined;
  const learning = outcome
    ? data?.kind === "compatibility"
      ? data.lessons.items.find((item) => item.related_journal_entry_id === outcome.id)
      : undefined
    : undefined;

  return (
    <DecisionChrome
      title="Paper execution"
      description="Simulated paper-order lifecycle. Canonical receipts use GET /canonical/executions/{id}. No live venue control is exposed."
      current="paper_execution"
    >
      {loading ? <LoadingState label="Loading paper execution…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {execution ? <ExecutionLifecycle execution={execution} /> : null}
      {data?.kind === "compatibility" ? (
        <OutcomeLearning
          outcome={
            outcome
              ? {
                  journalId: outcome.id,
                  positionId: outcome.linked_position_id ?? null,
                  proposalId: outcome.linked_proposal_id ?? null,
                  symbol: outcome.symbol,
                  result: outcome.result,
                  pnl: outcome.pnl ?? null,
                  lessons: outcome.lessons ?? null,
                  href: `/decision/outcomes/${outcome.id}`,
                }
              : null
          }
          learning={
            learning
              ? {
                  lessonId: learning.id,
                  status: learning.status,
                  lessonText: learning.lesson_text,
                  mistakeType: learning.mistake_type,
                  href: `/lessons?id=${learning.id}`,
                }
              : null
          }
        />
      ) : null}
    </DecisionChrome>
  );
}
