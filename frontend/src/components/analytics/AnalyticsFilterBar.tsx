"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import type { JournalTradeSource, PortfolioSourceFilter, UserStrategy } from "@/lib/api/types";

import { formatDateRangeLabel } from "./format";
import { JOURNAL_TRADE_SOURCE_OPTIONS } from "./filterValidation";
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
  journalSource: JournalTradeSource | "";
  setupId: string;
  userStrategyId: string;
};

function draftFromState(state: AnalyticsFilterState): Draft {
  return {
    dateFrom: state.dateFrom ?? "",
    dateTo: state.dateTo ?? "",
    symbol: state.symbol ?? "",
    timeframe: state.timeframe ?? "",
    portfolioSource: state.portfolioSource ?? "all",
    journalSource: state.journalSource ?? "",
    setupId: state.setupId ?? "",
    userStrategyId: state.userStrategyId ?? "",
  };
}

export type AnalyticsFilterBarProps = {
  state: AnalyticsFilterState;
  strategies?: UserStrategy[];
  strategiesLoading?: boolean;
  strategiesLoaded?: boolean;
  strategiesError?: string | null;
  onRetryStrategies?: () => void;
  onApplyDraft: (draft: {
    dateFrom?: string | null;
    dateTo?: string | null;
    symbol?: string | null;
    timeframe?: string | null;
    portfolioSource?: PortfolioSourceFilter | null;
    journalSource?: JournalTradeSource | null;
    setupId?: string | null;
    userStrategyId?: string | null;
  }) => void;
  onApplyPreset: (preset: DatePreset) => void;
  onClear: () => void;
};

export function AnalyticsFilterBar({
  state,
  strategies = [],
  strategiesLoading = false,
  strategiesLoaded = false,
  strategiesError = null,
  onRetryStrategies,
  onApplyDraft,
  onApplyPreset,
  onClear,
}: AnalyticsFilterBarProps) {
  const [draft, setDraft] = useState<Draft>(() => draftFromState(state));

  useEffect(() => {
    setDraft(draftFromState(state));
  }, [state]);

  const showPortfolioSource = state.tab === "performance";
  const showSetupFilters = state.tab === "setups";

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
        {showSetupFilters ? (
          <>
            <div className="space-y-1">
              <Label htmlFor="analytics-journal-source">Journal source</Label>
              <Select
                id="analytics-journal-source"
                value={draft.journalSource}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    journalSource: event.target.value as JournalTradeSource | "",
                  }))
                }
                data-testid="analytics-journal-source"
              >
                <option value="">All journal sources</option>
                {JOURNAL_TRADE_SOURCE_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="analytics-setup-id">Journal setup ID</Label>
              <Input
                id="analytics-setup-id"
                value={draft.setupId}
                placeholder="setup-definition UUID"
                onChange={(event) =>
                  setDraft((current) => ({ ...current, setupId: event.target.value }))
                }
                data-testid="analytics-setup-id"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="analytics-strategy-id">Strategy</Label>
              <Select
                id="analytics-strategy-id"
                value={draft.userStrategyId}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, userStrategyId: event.target.value }))
                }
                data-testid="analytics-strategy-id"
                disabled={strategiesLoading || Boolean(strategiesError)}
              >
                <option value="">
                  {strategiesLoading
                    ? "Loading strategies…"
                    : strategiesError
                      ? "Strategies unavailable"
                      : "All strategies"}
                </option>
                {!strategiesLoading &&
                  !strategiesError &&
                  strategies.map((strategy) => (
                    <option key={strategy.id} value={strategy.id}>
                      {strategy.name}
                    </option>
                  ))}
              </Select>
              {strategiesLoading ? (
                <p className="text-caption text-text-muted" data-testid="analytics-strategies-loading" role="status">
                  Loading strategy options…
                </p>
              ) : null}
              {strategiesError ? (
                <div
                  className="flex flex-wrap items-center gap-2 text-sm text-amber-500/90"
                  data-testid="analytics-strategies-error"
                  role="status"
                >
                  <span>Strategy options unavailable: {strategiesError}</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onRetryStrategies?.()}
                    data-testid="analytics-strategies-retry"
                  >
                    Retry strategies
                  </Button>
                </div>
              ) : null}
              {!strategiesLoading &&
              !strategiesError &&
              strategiesLoaded &&
              strategies.length === 0 ? (
                <p
                  className="text-caption text-text-muted"
                  data-testid="analytics-strategies-empty"
                  role="status"
                >
                  No strategies available
                </p>
              ) : null}
            </div>
          </>
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
              journalSource: showSetupFilters ? draft.journalSource || null : undefined,
              setupId: showSetupFilters ? draft.setupId.trim() || null : undefined,
              userStrategyId: showSetupFilters ? draft.userStrategyId.trim() || null : undefined,
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
        {showSetupFilters && state.journalSource ? ` · Source ${state.journalSource}` : ""}
        {showSetupFilters && state.setupId ? ` · setup_id ${state.setupId}` : ""}
        {showSetupFilters && state.userStrategyId
          ? ` · strategy ${state.userStrategyId}`
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
