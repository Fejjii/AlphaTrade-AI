"use client";

import { useCallback, useState } from "react";

import { CoachingPromptCard } from "@/components/coaching/CoachingPromptCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Input, Label } from "@/components/ui/input";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { CoachingCategory } from "@/lib/api/types";

const CATEGORY_FILTERS: { value: CoachingCategory | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "missed_entry", label: "Missed entry" },
  { value: "should_have_waited", label: "Should have waited" },
  { value: "should_have_avoided", label: "Should have avoided" },
  { value: "invalidation_hit", label: "Invalidation hit" },
  { value: "low_quality_setup", label: "Low quality" },
  { value: "overconfidence", label: "Overconfidence" },
  { value: "weak_confidence_correlation", label: "Weak confidence link" },
];

export default function CoachingPage() {
  const [filter, setFilter] = useState<CoachingCategory | "all">("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [minSample, setMinSample] = useState(5);

  const loader = useCallback(async () => {
    const dateParams = {
      ...(startDate ? { start_date: startDate } : {}),
      ...(endDate ? { end_date: endDate } : {}),
      min_sample: minSample,
    };
    const category = filter === "all" ? undefined : filter;
    const [summary, prompts] = await Promise.all([
      api.coaching.summary(dateParams),
      api.coaching.prompts({ ...dateParams, category, limit: 20 }),
    ]);
    return { summary, prompts };
  }, [filter, startDate, endDate, minSample]);

  const { data, loading, error, reload } = useAsyncData(loader, [filter, startDate, endDate, minSample]);

  return (
    <div className="space-y-8" data-testid="coaching-page">
      <div>
        <h1 className="text-2xl font-semibold">Coaching</h1>
        <p className="text-sm text-zinc-400">
          Deterministic behavior review prompts from your validation outcomes. Study discipline
          patterns — review this behavior, not trade advice. No orders, no automation.
        </p>
      </div>

      {loading && !data ? <LoadingState label="Loading coaching prompts…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        <>
          <section
            className="flex flex-wrap items-end gap-4 rounded-lg border border-zinc-800 p-4"
            data-testid="coaching-filters"
          >
            <div className="space-y-1">
              <Label htmlFor="coaching-start-date" className="text-xs text-zinc-400">
                From
              </Label>
              <Input
                id="coaching-start-date"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="coaching-end-date" className="text-xs text-zinc-400">
                To
              </Label>
              <Input
                id="coaching-end-date"
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="coaching-min-sample" className="text-xs text-zinc-400">
                Min sample
              </Label>
              <Input
                id="coaching-min-sample"
                type="number"
                min={1}
                max={100}
                value={minSample}
                onChange={(event) => setMinSample(Number(event.target.value) || 5)}
                className="w-24"
              />
            </div>
          </section>

          <section className="rounded-lg border border-zinc-800 p-4 text-sm" data-testid="coaching-summary">
            <p>
              Open patterns: <strong>{data.summary.total_open}</strong> · Pending coaching lessons:{" "}
              <strong>{data.summary.pending_coaching_lessons}</strong>
            </p>
          </section>

          <section className="space-y-3" data-testid="coaching-prompt-list">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-medium">Coaching prompts</h2>
              <div className="flex flex-wrap gap-1" role="group" aria-label="Category">
                {CATEGORY_FILTERS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    data-testid={`coaching-filter-${option.value}`}
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

            {data.prompts.items.length ? (
              <div className="grid gap-4 md:grid-cols-2">
                {data.prompts.items.map((prompt) => (
                  <CoachingPromptCard
                    key={prompt.signature}
                    prompt={prompt}
                    minSample={minSample}
                    startDate={startDate || undefined}
                    endDate={endDate || undefined}
                    onSaved={() => void reload()}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No coaching patterns yet"
                description="Complete more paper validation sessions with outcomes to surface behavior patterns."
              />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
