"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import type { PortfolioSourceFilter } from "@/lib/api/types";

import { formatDateRangeLabel } from "./format";
import type { AnalyticsFilterState, AnalyticsTab, DatePreset } from "./useAnalyticsFilters";

const PRESETS: { value: DatePreset; label: string }[] = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All time" },
];

const PP_SOURCE_OPTIONS: { value: PortfolioSourceFilter; label: string }[] = [
  { value: "all", label: "All paper sources" },
  { value: "proposal_flow", label: "Proposal flow" },
  { value: "paper_validation", label: "Paper validation" },
];

type Draft = {
  dateFrom: string;
  dateTo: string;
  symbol: string;
  timeframe: string;
  portfolioSource: PortfolioSourceFilter;
};

function draftFromState(state: AnalyticsFilterState): Draft {
  return {
    dateFrom: state.dateFrom ?? "",
    dateTo: state.dateTo ?? "",
    symbol: state.symbol ?? "",
    timeframe: state.timeframe ?? "",
    portfolioSource: state.portfolioSource ?? "all",
  };
}

export type AnalyticsFilterBarProps = {
  state: AnalyticsFilterState;
  onApplyDraft: (draft: {
    dateFrom?: string | null;
    dateTo?: string | null;
    symbol?: string | null;
    timeframe?: string | null;
    portfolioSource?: PortfolioSourceFilter | null;
  }) => void;
  onApplyPreset: (preset: DatePreset) => void;
  onClear: () => void;
};

export function AnalyticsFilterBar({
  state,
  onApplyDraft,
  onApplyPreset,
  onClear,
}: AnalyticsFilterBarProps) {
  const [draft, setDraft] = useState<Draft>(() => draftFromState(state));

  useEffect(() => {
    setDraft(draftFromState(state));
  }, [state]);

  const showPortfolioSource = state.tab === "performance";

  return (
    <section
      className="space-y-3 rounded-control border border-border-subtle bg-surface-0/40 p-4"
      data-testid="analytics-filter-bar"
      aria-label="Analytics filters"
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="analytics-date-from">From</Label>
          <Input
            id="analytics-date-from"
            type="date"
            value={draft.dateFrom}
            onChange={(event) => setDraft((current) => ({ ...current, dateFrom: event.target.value }))}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="analytics-date-to">To</Label>
          <Input
            id="analytics-date-to"
            type="date"
            value={draft.dateTo}
            onChange={(event) => setDraft((current) => ({ ...current, dateTo: event.target.value }))}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="analytics-symbol">Symbol</Label>
          <Input
            id="analytics-symbol"
            value={draft.symbol}
            placeholder="e.g. BTCUSDT"
            onChange={(event) => setDraft((current) => ({ ...current, symbol: event.target.value }))}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="analytics-timeframe">Timeframe</Label>
          <Input
            id="analytics-timeframe"
            value={draft.timeframe}
            placeholder="e.g. 1h"
            onChange={(event) =>
              setDraft((current) => ({ ...current, timeframe: event.target.value }))
            }
          />
        </div>
        {showPortfolioSource ? (
          <div className="space-y-1">
            <Label htmlFor="analytics-pp-source">Trade source</Label>
            <Select
              id="analytics-pp-source"
              value={draft.portfolioSource}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  portfolioSource: event.target.value as PortfolioSourceFilter,
                }))
              }
            >
              {PP_SOURCE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
        <Button
          type="button"
          onClick={() =>
            onApplyDraft({
              dateFrom: draft.dateFrom || null,
              dateTo: draft.dateTo || null,
              symbol: draft.symbol.trim() || null,
              timeframe: draft.timeframe.trim() || null,
              portfolioSource: showPortfolioSource ? draft.portfolioSource : null,
            })
          }
          data-testid="analytics-apply-filters"
        >
          Apply filters
        </Button>
        <Button type="button" variant="outline" onClick={onClear} data-testid="analytics-clear-filters">
          Clear
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-caption text-text-muted">Presets:</span>
        {PRESETS.map((preset) => (
          <Button
            key={preset.value}
            type="button"
            size="sm"
            variant="outline"
            data-testid={`analytics-preset-${preset.value}`}
            onClick={() => onApplyPreset(preset.value)}
          >
            {preset.label}
          </Button>
        ))}
      </div>

      <p className="text-caption text-text-muted" data-testid="analytics-filter-summary">
        Range: {formatDateRangeLabel(state.dateFrom, state.dateTo)}
        {state.symbol ? ` · Symbol ${state.symbol}` : ""}
        {state.timeframe ? ` · Timeframe ${state.timeframe}` : ""}
        {showPortfolioSource && state.portfolioSource && state.portfolioSource !== "all"
          ? ` · Source ${state.portfolioSource}`
          : ""}
      </p>

      {state.ignoredParams.length ? (
        <p className="text-sm text-amber-500/90" data-testid="analytics-ignored-filters" role="status">
          Ignored invalid filter{state.ignoredParams.length > 1 ? "s" : ""}:{" "}
          {state.ignoredParams.join(", ")}
        </p>
      ) : null}
    </section>
  );
}

export type { AnalyticsTab, DatePreset };
