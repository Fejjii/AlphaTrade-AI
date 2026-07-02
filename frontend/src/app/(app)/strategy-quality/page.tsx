"use client";

import { useCallback, useState } from "react";

import { DetectorQualityCard } from "@/components/strategy-quality/DetectorQualityCard";
import { DetectorQualitySummary } from "@/components/strategy-quality/DetectorQualitySummary";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Input, Label } from "@/components/ui/input";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function StrategyQualityPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const loader = useCallback(async () => {
    const dateParams = {
      ...(startDate ? { start_date: startDate } : {}),
      ...(endDate ? { end_date: endDate } : {}),
    };
    const [summary, detectors] = await Promise.all([
      api.strategyQuality.summary(dateParams),
      api.strategyQuality.detectors(dateParams),
    ]);
    return { summary, detectors };
  }, [startDate, endDate]);

  const { data, loading, error, reload } = useAsyncData(loader, [startDate, endDate]);

  return (
    <div className="space-y-8" data-testid="strategy-quality-page">
      <div>
        <h1 className="text-2xl font-semibold">Strategy Quality</h1>
        <p className="text-sm text-zinc-400">
          Read-only detector performance from your paper validation outcomes. Use it to decide
          which setup detectors to trust, improve, or avoid for now. Human study aid only — it does
          not change strategy rules, enable or disable detectors, recommend live trades, or run any
          automation.
        </p>
      </div>

      {loading && !data ? <LoadingState label="Loading strategy quality…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        <>
          <section
            className="flex flex-wrap items-end gap-4 rounded-lg border border-zinc-800 p-4"
            data-testid="strategy-quality-date-range"
          >
            <div className="space-y-1">
              <Label htmlFor="strategy-quality-start-date" className="text-xs text-zinc-400">
                History from
              </Label>
              <Input
                id="strategy-quality-start-date"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="strategy-quality-end-date" className="text-xs text-zinc-400">
                History to
              </Label>
              <Input
                id="strategy-quality-end-date"
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="w-40"
              />
            </div>
            <p className="text-xs text-zinc-500">
              Optional — filters the validated outcomes used to score each detector.
            </p>
          </section>

          <DetectorQualitySummary summary={data.summary} />

          <section className="space-y-3" data-testid="strategy-quality-detectors">
            <h2 className="text-lg font-medium">Detectors</h2>
            {data.detectors.detectors.length ? (
              <div className="grid gap-4 md:grid-cols-2">
                {data.detectors.detectors.map((report) => (
                  <DetectorQualityCard key={report.condition} report={report} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No detectors to review"
                description="Record paper validation outcomes to build detector quality scores."
              />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
