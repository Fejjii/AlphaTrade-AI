"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { ClosedJournalTrades } from "@/components/journal/ClosedJournalTrades";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TradingMetric } from "@/components/dashboard/TradingMetric";
import { Input, Label, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { VerifiedPaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type {
  CanonicalJournalTradeListItem,
  ExecutionActor,
  JournalStatsGroupBy,
  JournalStatsParams,
  JournalTradeSource,
  JournalTradeStatsMetrics,
  MarketRegime,
  PaginatedCanonicalJournalTrades,
  SampleConfidence,
  TradeRuleCompliance,
} from "@/lib/api/types";
import {
  formatCount,
  formatMonetary,
  formatPercent,
  formatProfitFactor,
  humanizeToken,
  UNAVAILABLE,
} from "@/lib/format";

const GROUP_BY_OPTIONS: { value: JournalStatsGroupBy; label: string }[] = [
  { value: "overall", label: "Overall" },
  { value: "setup", label: "Setup" },
  { value: "setup_version", label: "Setup version" },
  { value: "strategy", label: "Strategy" },
  { value: "strategy_version", label: "Strategy version" },
  { value: "symbol", label: "Symbol" },
  { value: "timeframe", label: "Timeframe" },
  { value: "market_regime", label: "Market regime" },
  { value: "source", label: "Source" },
  { value: "entry_method", label: "Entry method" },
  { value: "rule_compliance", label: "Rule compliance" },
  { value: "execution_actor", label: "Human vs system" },
];

const SOURCE_OPTIONS: JournalTradeSource[] = [
  "manual",
  "paper_execution",
  "paper_validation",
  "backtest",
  "imported",
  "system",
];

const REGIME_OPTIONS: MarketRegime[] = [
  "trending_up",
  "trending_down",
  "ranging",
  "volatile",
  "quiet",
  "unknown",
];

const COMPLIANCE_OPTIONS: TradeRuleCompliance[] = [
  "compliant",
  "partial",
  "violated",
  "unassessed",
];

const CONFIDENCE_TONE: Record<SampleConfidence, "ok" | "warn" | "critical"> = {
  high: "ok",
  moderate: "ok",
  low: "warn",
  insufficient: "critical",
};

const BUCKET_PAGE_SIZE = 20;

function pct(value: number | null): string {
  return formatPercent(value);
}

function num(value: number | null, digits = 2): string {
  if (value === null) return "—";
  return value.toFixed(digits);
}

function ConfidenceBadge({ confidence }: { confidence: SampleConfidence }) {
  return (
    <StatusBadge
      label={humanizeToken(confidence)}
      tone={CONFIDENCE_TONE[confidence]}
    />
  );
}

function MetricsSummary({ metrics }: { metrics: JournalTradeStatsMetrics }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <TradingMetric
          label="Closed trades"
          value={formatCount(metrics.trade_count)}
          note={`${metrics.wins} wins · ${metrics.losses} losses · ${metrics.breakeven} breakeven`}
        />
        <TradingMetric
          label="Net PnL"
          value={formatMonetary(metrics.net_pnl_total)}
          amount={metrics.net_pnl_total}
          note={`Recorded PnL on ${metrics.pnl_sample_count} trades`}
        />
        <TradingMetric
          label="Win rate"
          value={metrics.trade_count > 0 ? pct(metrics.win_rate) : UNAVAILABLE}
          note={
            metrics.trade_count > 0
              ? "Closed-trade outcomes"
              : "No closed trades yet"
          }
        />
        <TradingMetric
          label="Expectancy"
          value={
            metrics.pnl_sample_count > 0
              ? formatMonetary(metrics.expectancy)
              : UNAVAILABLE
          }
          amount={metrics.expectancy}
          note={
            metrics.pnl_sample_count > 0
              ? `Per trade · ${metrics.pnl_sample_count} PnL samples`
              : "No recorded PnL samples"
          }
        />
      </div>
      <details className="rounded-control border border-border-subtle p-3">
        <summary className="cursor-pointer text-sm font-medium text-text-secondary">
          Risk, costs, and trade capture
        </summary>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-text-secondary">Average R</dt>
            <dd className="mt-1 font-data">
              {num(metrics.average_r)} · {metrics.r_sample_count} samples
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-secondary">Profit factor</dt>
            <dd className="mt-1 font-data">
              {formatProfitFactor(
                metrics.profit_factor,
                metrics.warnings.map((w) => w.code),
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-secondary">Average winner</dt>
            <dd className="mt-1 font-data">
              {formatMonetary(metrics.average_winner)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-secondary">Average loser</dt>
            <dd className="mt-1 font-data">
              {formatMonetary(metrics.average_loser)}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-text-secondary">
              Costs · {metrics.cost_sample_count} samples
            </dt>
            <dd className="mt-1">
              {formatMonetary(metrics.total_costs)} total · fees{" "}
              {formatMonetary(metrics.fees_total)} · funding{" "}
              {formatMonetary(metrics.funding_total)} · slippage{" "}
              {formatMonetary(metrics.slippage_total)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-secondary">Average MFE</dt>
            <dd className="mt-1 font-data">
              {formatMonetary(metrics.average_mfe_amount)} ·{" "}
              {metrics.mfe_sample_count} samples
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-secondary">Average MAE</dt>
            <dd className="mt-1 font-data">
              {formatMonetary(metrics.average_mae_amount)} ·{" "}
              {metrics.mae_sample_count} samples
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-text-secondary">
              Realized vs available
            </dt>
            <dd className="mt-1 font-data">
              {metrics.average_realized_vs_available_pct == null
                ? UNAVAILABLE
                : `${metrics.average_realized_vs_available_pct.toFixed(1)}%`}{" "}
              · {metrics.capture_sample_count} samples
            </dd>
          </div>
        </dl>
      </details>
    </div>
  );
}

export default function JournalStatisticsPage() {
  const [groupBy, setGroupBy] = useState<JournalStatsGroupBy>("setup_version");
  const [source, setSource] = useState<JournalTradeSource | "">("");
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [regime, setRegime] = useState<MarketRegime | "">("");
  const [compliance, setCompliance] = useState<TradeRuleCompliance | "">("");
  const [actor, setActor] = useState<ExecutionActor | "">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);

  const loader = useCallback(() => {
    const params: JournalStatsParams = {
      group_by: groupBy,
      source: source || undefined,
      symbol: symbol.trim() || undefined,
      timeframe: timeframe.trim() || undefined,
      market_regime: regime || undefined,
      rule_compliance: compliance || undefined,
      execution_actor: actor || undefined,
      date_from: dateFrom ? `${dateFrom}T00:00:00Z` : undefined,
      date_to: dateTo ? `${dateTo}T23:59:59Z` : undefined,
      limit: BUCKET_PAGE_SIZE,
      offset,
    };
    return api.journal.statistics(params);
  }, [
    groupBy,
    source,
    symbol,
    timeframe,
    regime,
    compliance,
    actor,
    dateFrom,
    dateTo,
    offset,
  ]);
  const { data, loading, error, reload } = useAsyncData(loader, [loader]);
  const tradeLoader = useCallback(
    () =>
      api.journal.listTrades({
        status: "closed",
        source: "paper_execution",
        limit: 20,
      }),
    [],
  );
  const tradesState = useAsyncData(tradeLoader, [tradeLoader]);
  const closedTrades = closedTradeItems(tradesState.data);

  return (
    <div className="space-y-section [&_input]:min-w-0 [&_input]:text-base [&_select]:text-base lg:[&_input]:text-sm lg:[&_select]:text-sm">
      <PageHeader
        title="Journal statistics"
        description="Closed-trade performance, sample confidence, and the cost of each decision. Recorded values only."
        meta={<VerifiedPaperModeIndicator />}
      />

      <nav
        aria-label="Journal review"
        className="flex flex-wrap gap-2 border-b border-border-subtle pb-3 text-sm"
      >
        <Link
          href="/journal"
          className="inline-flex min-h-11 items-center px-3 text-text-secondary hover:text-text-primary"
        >
          Review
        </Link>
        <Link
          href="/journal/statistics"
          aria-current="page"
          className="inline-flex min-h-11 items-center rounded-control bg-surface-2 px-3 font-medium"
        >
          Statistics
        </Link>
      </nav>
      <div className="rounded-card border border-border-subtle bg-surface-1/50 p-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-2">
            <Label htmlFor="stats-group-by">Group by</Label>
            <Select
              id="stats-group-by"
              value={groupBy}
              onChange={(e) => {
                setGroupBy(e.target.value as JournalStatsGroupBy);
                setOffset(0);
              }}
            >
              {GROUP_BY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="stats-source">Source</Label>
            <Select
              id="stats-source"
              value={source}
              onChange={(e) => {
                setSource(e.target.value as JournalTradeSource | "");
                setOffset(0);
              }}
            >
              <option value="">All sources</option>
              {SOURCE_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {humanizeToken(value)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="stats-symbol">Symbol</Label>
            <Input
              id="stats-symbol"
              placeholder="e.g. BTCUSDT"
              value={symbol}
              onChange={(e) => {
                setSymbol(e.target.value.toUpperCase());
                setOffset(0);
              }}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="stats-timeframe">Timeframe</Label>
            <Input
              id="stats-timeframe"
              placeholder="e.g. 1h"
              value={timeframe}
              onChange={(e) => {
                setTimeframe(e.target.value);
                setOffset(0);
              }}
            />
          </div>
        </div>
        <details className="mt-4 border-t border-border-subtle pt-3">
          <summary className="cursor-pointer text-sm font-medium text-text-secondary">
            More filters · regime, compliance, actor, and dates
          </summary>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="stats-regime">Market regime</Label>
              <Select
                id="stats-regime"
                value={regime}
                onChange={(e) => {
                  setRegime(e.target.value as MarketRegime | "");
                  setOffset(0);
                }}
              >
                <option value="">All regimes</option>
                {REGIME_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {humanizeToken(value)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="stats-compliance">Rule compliance</Label>
              <Select
                id="stats-compliance"
                value={compliance}
                onChange={(e) => {
                  setCompliance(e.target.value as TradeRuleCompliance | "");
                  setOffset(0);
                }}
              >
                <option value="">All trades</option>
                {COMPLIANCE_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {humanizeToken(value)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="stats-actor">Execution</Label>
              <Select
                id="stats-actor"
                value={actor}
                onChange={(e) => {
                  setActor(e.target.value as ExecutionActor | "");
                  setOffset(0);
                }}
              >
                <option value="">Human + system</option>
                <option value="human">Human</option>
                <option value="system">System</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="stats-date-from">From</Label>
              <Input
                id="stats-date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="stats-date-to">To</Label>
              <Input
                id="stats-date-to"
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
          </div>
        </details>
      </div>

      {loading ? <LoadingState label="Loading journal statistics…" /> : null}
      {error ? (
        <ErrorState message={error} onRetry={() => void reload()} />
      ) : null}

      {data && !loading && !error ? (
        <>
          {data.truncated ? (
            <p
              role="status"
              className="rounded-control border border-warning-border bg-warning-muted p-3 text-sm text-warning"
            >
              Result capped at {data.max_rows} closed trades — aggregates are
              partial. Narrow the date range or filters.
            </p>
          ) : null}

          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">Overall (filtered)</CardTitle>
              <ConfidenceBadge confidence={data.overall.confidence} />
            </CardHeader>
            <CardContent className="space-y-3">
              <MetricsSummary metrics={data.overall} />
              {data.overall.warnings.length ? (
                <ul className="list-disc space-y-1 rounded-control border border-warning-border bg-warning-muted py-3 pl-7 pr-3 text-sm text-warning">
                  {data.overall.warnings.map((w) => (
                    <li key={w.code}>{w.message}</li>
                  ))}
                </ul>
              ) : null}
            </CardContent>
          </Card>

          {data.group_by !== "overall" ? (
            <section className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-medium">
                  {
                    GROUP_BY_OPTIONS.find((o) => o.value === data.group_by)
                      ?.label
                  }{" "}
                  breakdown ({data.total_buckets} groups)
                </h2>
                {data.total_buckets > BUCKET_PAGE_SIZE ? (
                  <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={offset === 0}
                      onClick={() =>
                        setOffset(Math.max(0, offset - BUCKET_PAGE_SIZE))
                      }
                    >
                      Previous
                    </Button>
                    <span>
                      {offset + 1}–
                      {Math.min(offset + BUCKET_PAGE_SIZE, data.total_buckets)}
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={offset + BUCKET_PAGE_SIZE >= data.total_buckets}
                      onClick={() => setOffset(offset + BUCKET_PAGE_SIZE)}
                    >
                      Next
                    </Button>
                  </div>
                ) : null}
              </div>
              {data.buckets.length ? (
                <div className="grid gap-4 lg:grid-cols-2">
                  {data.buckets.map((bucket) => (
                    <Card key={bucket.key}>
                      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
                        <CardTitle className="min-w-0 break-words text-base">
                          {bucket.label}
                        </CardTitle>
                        <ConfidenceBadge
                          confidence={bucket.metrics.confidence}
                        />
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <MetricsSummary metrics={bucket.metrics} />
                        {bucket.metrics.warnings.length ? (
                          <ul className="list-disc space-y-1 rounded-control border border-warning-border bg-warning-muted py-3 pl-7 pr-3 text-sm text-warning">
                            {bucket.metrics.warnings.map((w) => (
                              <li key={w.code}>{w.message}</li>
                            ))}
                          </ul>
                        ) : null}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No closed journal trades"
                  description="Close canonical journal trades (manual, paper, or imported) to build statistics."
                />
              )}
            </section>
          ) : null}
        </>
      ) : null}
      <p className="text-xs text-text-secondary">
        Recent closed paper trades · this list is independent of the statistics
        filters.
      </p>
      {tradesState.loading ? (
        <LoadingState label="Loading closed paper trades…" />
      ) : tradesState.error ? (
        <ErrorState
          message={`Closed paper trades unavailable: ${tradesState.error}`}
          onRetry={() => void tradesState.reload()}
        />
      ) : (
        <ClosedJournalTrades trades={closedTrades} />
      )}
    </div>
  );
}

function closedTradeItems(
  data: PaginatedCanonicalJournalTrades | null,
): CanonicalJournalTradeListItem[] {
  if (!data || !Array.isArray(data.items)) return [];
  return data.items;
}
