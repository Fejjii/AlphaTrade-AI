"use client";

import { useCallback, useState } from "react";

import { PriorityItemCard } from "@/components/validation-priority/PriorityItemCard";
import { PriorityQueueSummary } from "@/components/validation-priority/PriorityQueueSummary";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Input, Label } from "@/components/ui/input";
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
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const loader = useCallback(async () => {
    const itemType = filter === "all" ? undefined : filter;
    const dateParams = {
      ...(startDate ? { start_date: startDate } : {}),
      ...(endDate ? { end_date: endDate } : {}),
    };
    const [summary, queue] = await Promise.all([
      api.validationPriority.summary(dateParams),
      api.validationPriority.queue({ item_type: itemType, ...dateParams }),
    ]);
    return { summary, queue };
  }, [filter, startDate, endDate]);

  const { data, loading, error, reload } = useAsyncData(loader, [filter, startDate, endDate]);

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
          <section
            className="flex flex-wrap items-end gap-4 rounded-lg border border-zinc-800 p-4"
            data-testid="validation-priority-date-range"
          >
            <div className="space-y-1">
              <Label htmlFor="validation-priority-start-date" className="text-xs text-zinc-400">
                History from
              </Label>
              <Input
                id="validation-priority-start-date"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="validation-priority-end-date" className="text-xs text-zinc-400">
                History to
              </Label>
              <Input
                id="validation-priority-end-date"
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="w-40"
              />
            </div>
            <p className="text-xs text-zinc-500">
              Optional — filters historical evidence only; pending items are always ranked.
            </p>
          </section>

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
