"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { humanizeToken } from "@/lib/format";
import type {
  JournalTradeSource,
  MarketRegime,
  PortfolioSourceFilter,
  TradeRuleCompliance,
  UserStrategy,
} from "@/lib/api/types";

import { formatDateRangeLabel } from "./format";
import {
  DEFAULT_VALIDATION_MIN_SAMPLE,
  JOURNAL_TRADE_SOURCE_OPTIONS,
  validateMinSampleInput,
} from "./filterValidation";
import { VALIDATION_DIMENSION_LABELS } from "./validationDimensionCopy";
import type { AnalyticsDraft, AnalyticsFilterState, AnalyticsTab, DatePreset } from "./useAnalyticsFilters";

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

const RULE_COMPLIANCE_OPTIONS: { value: "" | TradeRuleCompliance; label: string }[] = [
  { value: "", label: "All compliance" },
  { value: "compliant", label: "Compliant" },
  { value: "partial", label: "Partial" },
  { value: "violated", label: "Violated" },
  { value: "unassessed", label: "Unassessed" },
];

const REGIME_OPTIONS: { value: "" | MarketRegime; label: string }[] = [
  { value: "", label: "All regimes" },
  { value: "trending_up", label: "Trending up" },
  { value: "trending_down", label: "Trending down" },
  { value: "ranging", label: "Ranging" },
  { value: "volatile", label: "Volatile" },
  { value: "quiet", label: "Quiet" },
  { value: "unknown", label: "Unknown" },
];

function portfolioSourceLabel(value: PortfolioSourceFilter): string {
  return PP_SOURCE_OPTIONS.find((option) => option.value === value)?.label ?? humanizeToken(value);
}

function ruleComplianceLabel(value: TradeRuleCompliance): string {
  return RULE_COMPLIANCE_OPTIONS.find((option) => option.value === value)?.label ?? humanizeToken(value);
}

function regimeLabel(value: MarketRegime): string {
  return REGIME_OPTIONS.find((option) => option.value === value)?.label ?? humanizeToken(value);
}

function strategySummaryLabel(
  state: AnalyticsFilterState,
  strategies: UserStrategy[],
): string | null {
  if (!state.userStrategyId) return null;
  const match = strategies.find((strategy) => strategy.id === state.userStrategyId);
  return match ? `Strategy ${match.name}` : `Strategy ${state.userStrategyId}`;
}

type Draft = {
  dateFrom: string;
  dateTo: string;
  symbol: string;
  timeframe: string;
  portfolioSource: PortfolioSourceFilter;
  journalSource: JournalTradeSource | "";
  setupId: string;
  userStrategyId: string;
  ruleCompliance: "" | TradeRuleCompliance;
  marketRegime: "" | MarketRegime;
  minSample: string;
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
    ruleCompliance: state.ruleCompliance ?? "",
    marketRegime: state.marketRegime ?? "",
    minSample: String(state.minSample),
  };
}

export type AnalyticsFilterBarProps = {
  state: AnalyticsFilterState;
  strategies?: UserStrategy[];
  strategiesLoading?: boolean;
  strategiesLoaded?: boolean;
  strategiesError?: string | null;
  onRetryStrategies?: () => void;
  onApplyDraft: (draft: AnalyticsDraft) => void;
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
  const [minSampleError, setMinSampleError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(draftFromState(state));
    setMinSampleError(null);
  }, [state]);

  const showPortfolioSource = state.tab === "performance";
  const showSetupsFilters = state.tab === "setups";
  const showBehaviourFilters = state.tab === "behaviour";
  const showComparisonFilters = state.tab === "comparison";
  const showValidationFilters = state.tab === "validation";
  const showSharedSymbolTimeframe = !showValidationFilters;
  const showJournalIdentityFilters =
    showSetupsFilters || showBehaviourFilters || showComparisonFilters;

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
        {showSharedSymbolTimeframe ? (
          <>
            <div className="space-y-1">
              <Label htmlFor="analytics-symbol">Symbol</Label>
              <Input
                id="analytics-symbol"
                value={draft.symbol}
                placeholder="e.g. BTCUSDT"
                onChange={(event) =>
                  setDraft((current) => ({ ...current, symbol: event.target.value }))
                }
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
          </>
        ) : null}
        {showValidationFilters ? (
          <div className="space-y-1">
            <Label htmlFor="analytics-min-sample">Min sample</Label>
            <Input
              id="analytics-min-sample"
              type="number"
              min={1}
              max={100}
              value={draft.minSample}
              onChange={(event) => {
                setMinSampleError(null);
                setDraft((current) => ({ ...current, minSample: event.target.value }));
              }}
              data-testid="analytics-min-sample"
              aria-invalid={minSampleError ? true : undefined}
              aria-describedby={minSampleError ? "analytics-min-sample-error" : undefined}
            />
            {minSampleError ? (
              <p
                id="analytics-min-sample-error"
                className="text-sm text-amber-500/90"
                data-testid="analytics-min-sample-error"
                role="alert"
              >
                {minSampleError}
              </p>
            ) : null}
          </div>
        ) : null}
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
        {showJournalIdentityFilters ? (
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
                    {humanizeToken(value)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="analytics-setup-id">Journal setup</Label>
              <Input
                id="analytics-setup-id"
                value={draft.setupId}
                placeholder="Setup identifier"
                onChange={(event) =>
                  setDraft((current) => ({ ...current, setupId: event.target.value }))
                }
                data-testid="analytics-setup-id"
              />
            </div>
          </>
        ) : null}
        {showSetupsFilters ? (
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
              <p
                className="text-caption text-text-muted"
                data-testid="analytics-strategies-loading"
                role="status"
              >
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
        ) : null}
        {(showBehaviourFilters || showComparisonFilters) && !showSetupsFilters ? (
          <div className="space-y-1">
            <Label htmlFor="analytics-user-strategy-id">Strategy</Label>
            <Input
              id="analytics-user-strategy-id"
              value={draft.userStrategyId}
              placeholder="Strategy identifier"
              onChange={(event) =>
                setDraft((current) => ({ ...current, userStrategyId: event.target.value }))
              }
              data-testid="analytics-user-strategy-id"
            />
          </div>
        ) : null}
        {showBehaviourFilters ? (
          <div className="space-y-1">
            <Label htmlFor="analytics-rule-compliance">Rule compliance</Label>
            <Select
              id="analytics-rule-compliance"
              value={draft.ruleCompliance}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  ruleCompliance: event.target.value as "" | TradeRuleCompliance,
                }))
              }
              data-testid="analytics-rule-compliance"
            >
              {RULE_COMPLIANCE_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
        {showComparisonFilters ? (
          <div className="space-y-1">
            <Label htmlFor="analytics-market-regime">Market regime</Label>
            <Select
              id="analytics-market-regime"
              value={draft.marketRegime}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  marketRegime: event.target.value as "" | MarketRegime,
                }))
              }
              data-testid="analytics-market-regime"
            >
              {REGIME_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
        <Button
          type="button"
          onClick={() => {
            const next: AnalyticsDraft = {
              dateFrom: draft.dateFrom || null,
              dateTo: draft.dateTo || null,
            };
            if (showSharedSymbolTimeframe) {
              next.symbol = draft.symbol.trim() || null;
              next.timeframe = draft.timeframe.trim() || null;
            }
            if (showPortfolioSource) next.portfolioSource = draft.portfolioSource;
            if (showJournalIdentityFilters) {
              next.journalSource = draft.journalSource || null;
              next.setupId = draft.setupId.trim() || null;
            }
            if (showSetupsFilters || showBehaviourFilters || showComparisonFilters) {
              next.userStrategyId = draft.userStrategyId.trim() || null;
            }
            if (showBehaviourFilters) next.ruleCompliance = draft.ruleCompliance || null;
            if (showComparisonFilters) next.marketRegime = draft.marketRegime || null;
            if (showValidationFilters) {
              const minSampleResult = validateMinSampleInput(draft.minSample);
              if (!minSampleResult.valid) {
                setMinSampleError(minSampleResult.message);
                return;
              }
              setMinSampleError(null);
              next.minSample =
                minSampleResult.value === DEFAULT_VALIDATION_MIN_SAMPLE
                  ? null
                  : minSampleResult.value;
            }
            onApplyDraft(next);
          }}
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
        {showSharedSymbolTimeframe && state.symbol ? ` · Symbol ${state.symbol}` : ""}
        {showSharedSymbolTimeframe && state.timeframe ? ` · Timeframe ${state.timeframe}` : ""}
        {showPortfolioSource && state.portfolioSource && state.portfolioSource !== "all"
          ? ` · ${portfolioSourceLabel(state.portfolioSource)}`
          : ""}
        {showSetupsFilters && state.journalSource
          ? ` · Journal source ${humanizeToken(state.journalSource)}`
          : ""}
        {showSetupsFilters && state.setupId ? ` · Setup ${state.setupId}` : ""}
        {showSetupsFilters && state.userStrategyId
          ? ` · ${strategySummaryLabel(state, strategies) ?? `Strategy ${state.userStrategyId}`}`
          : ""}
        {showBehaviourFilters && state.journalSource
          ? ` · Journal source ${humanizeToken(state.journalSource)}`
          : ""}
        {showBehaviourFilters && state.setupId ? ` · Setup ${state.setupId}` : ""}
        {showBehaviourFilters && state.userStrategyId
          ? ` · Strategy ${state.userStrategyId}`
          : ""}
        {showBehaviourFilters && state.ruleCompliance
          ? ` · Compliance ${ruleComplianceLabel(state.ruleCompliance)}`
          : ""}
        {showComparisonFilters && state.journalSource
          ? ` · Journal source ${humanizeToken(state.journalSource)}`
          : ""}
        {showComparisonFilters && state.setupId ? ` · Setup ${state.setupId}` : ""}
        {showComparisonFilters && state.userStrategyId
          ? ` · Strategy ${state.userStrategyId}`
          : ""}
        {showComparisonFilters && state.marketRegime
          ? ` · Regime ${regimeLabel(state.marketRegime)}`
          : ""}
        {showValidationFilters ? ` · Min sample ${state.minSample}` : ""}
        {showValidationFilters
          ? ` · Dimension ${VALIDATION_DIMENSION_LABELS[state.dimension] ?? humanizeToken(state.dimension)}`
          : ""}
      </p>

      {showValidationFilters ? (
        <p className="text-caption text-text-muted" data-testid="analytics-validation-filter-note">
          Validation views use the date range and minimum sample size. Setup performance and setup
          ranking also use the selected dimension. Journal and portfolio filters are not applied on
          this tab.
        </p>
      ) : null}

      {showJournalIdentityFilters ? (
        <p className="text-caption text-text-muted" data-testid="analytics-setup-identity-note">
          Journal setup filters apply to journal statistics only. They are not sent to portfolio
          views and are not translated by setup name.
        </p>
      ) : null}

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
