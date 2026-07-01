"use client";

import { useCallback, useState } from "react";

import { PriorityItemCard } from "@/components/validation-priority/PriorityItemCard";
import { PriorityQueueSummary } from "@/components/validation-priority/PriorityQueueSummary";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { PriorityItemType } from "@/lib/api/types";

const FILTERS: { value: PriorityItemType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "run_plan", label: "Run plans" },
  { value: "candidate", label: "Candidates" },
];

export default function ValidationPriorityPage() {
  const [filter, setFilter] = useState<PriorityItemType | "all">("all");

  const loader = useCallback(async () => {
    const itemType = filter === "all" ? undefined : filter;
    const [summary, queue] = await Promise.all([
      api.validationPriority.summary(),
      api.validationPriority.queue({ item_type: itemType }),
    ]);
    return { summary, queue };
  }, [filter]);

  const { data, loading, error, reload } = useAsyncData(loader, [filter]);

  return (
    <div className="space-y-8" data-testid="validation-priority-page">
      <div>
        <h1 className="text-2xl font-semibold">Validation Priority</h1>
        <p className="text-sm text-zinc-400">
          Read-only ranking of pending run plans and candidates to help you choose what to validate
          next. Human study aid only — no orders, no proposals, no automation.
        </p>
      </div>

      {loading && !data ? <LoadingState label="Loading validation priority…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        <>
          <PriorityQueueSummary summary={data.summary} />

          <section className="space-y-3" data-testid="validation-priority-queue">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-medium">Ranked queue</h2>
              <div className="flex flex-wrap gap-1" role="group" aria-label="Item type">
                {FILTERS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    data-testid={`validation-priority-filter-${option.value}`}
                    onClick={() => setFilter(option.value)}
                    className={
                      filter === option.value
                        ? "rounded bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-900"
                        : "rounded border border-zinc-700 px-3 py-1 text-xs text-zinc-300"
                    }
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {data.queue.items.length ? (
              <div className="grid gap-4 md:grid-cols-2">
                {data.queue.items.map((item) => (
                  <PriorityItemCard key={item.item_id} item={item} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No pending setups"
                description="Queue a candidate or plan a validation run to see prioritization."
              />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
