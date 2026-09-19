"use client";

import { useCallback, useMemo } from "react";
import Link from "next/link";

import { DecisionCaseCard } from "@/components/canonical-decision/DecisionCaseCard";
import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { buttonVariants } from "@/components/ui/button";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { composeDecisionCases } from "@/lib/canonical-decision/compose";
import { loadSource, type SourceResult } from "@/components/workflows";
import { cn } from "@/lib/utils";

type HubSources = {
  candidates: SourceResult<Awaited<ReturnType<typeof api.strategies.candidates>>>;
  proposals: SourceResult<Awaited<ReturnType<typeof api.proposals.list>>>;
  approvals: SourceResult<Awaited<ReturnType<typeof api.approvals.list>>>;
  orders: SourceResult<Awaited<ReturnType<typeof api.execution.listOrders>>>;
  journals: SourceResult<Awaited<ReturnType<typeof api.journal.list>>>;
  lessons: SourceResult<Awaited<ReturnType<typeof api.lessons.listCandidates>>>;
};

export default function DecisionHubPage() {
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();

  const loader = useCallback(async (): Promise<HubSources> => {
    const [candidates, proposals, approvals, orders, journals, lessons] = await Promise.all([
      loadSource(api.strategies.candidates({ limit: 50 })),
      loadSource(api.proposals.list({ limit: 50 })),
      loadSource(api.approvals.list({ limit: 50 })),
      loadSource(api.execution.listOrders({ limit: 50 })),
      loadSource(api.journal.list({ limit: 50 })),
      loadSource(api.lessons.listCandidates()),
    ]);
    return { candidates, proposals, approvals, orders, journals, lessons };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const snapshot = useMemo(() => {
    if (!data) return null;
    return composeDecisionCases({
      candidates: data.candidates.data?.items ?? [],
      proposals: data.proposals.data?.items ?? [],
      approvals: data.approvals.data?.items ?? [],
      orders: data.orders.data?.items ?? [],
      journals: data.journals.data?.items ?? [],
      lessons: data.lessons.data?.items ?? [],
      killSwitchActive,
      executionMode,
      realTradingEnabled,
    });
  }, [data, killSwitchActive, executionMode, realTradingEnabled]);

  return (
    <DecisionChrome
      title="Decision"
      description="Paper-only canonical loop: market quality, candidate, eligibility, TradePlan, human approval, paper execution, outcome, and learning."
      current="candidate"
      eligibilityBlocked={killSwitchActive}
    >
      <div className="flex flex-wrap gap-2">
        <Link href="/decision/market" className={cn(buttonVariants({ variant: "secondary" }), "min-h-11")}>
          Market assessment
        </Link>
        <Link href="/decision/candidates" className={cn(buttonVariants({ variant: "secondary" }), "min-h-11")}>
          Candidates
        </Link>
        <Link href="/decision/strategy" className={cn(buttonVariants({ variant: "secondary" }), "min-h-11")}>
          Strategy performance
        </Link>
        <Link href="/workspace" className={cn(buttonVariants({ variant: "ghost" }), "min-h-11")}>
          Legacy AI assist
        </Link>
        <Link href="/approvals" className={cn(buttonVariants({ variant: "ghost" }), "min-h-11")}>
          Legacy approvals
        </Link>
      </div>

      {loading ? <LoadingState label="Loading decision queue…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {snapshot && snapshot.cases.length === 0 ? (
        <EmptyState
          title="No paper decisions yet"
          description="Market assessment, validation candidates, and proposals will appear here. Nothing here can place a live order."
        />
      ) : null}

      {snapshot?.cases.length ? (
        <section className="grid gap-4" data-testid="decision-queue">
          {snapshot.cases.map((item) => (
            <DecisionCaseCard key={item.id} item={item} />
          ))}
        </section>
      ) : null}
    </DecisionChrome>
  );
}
