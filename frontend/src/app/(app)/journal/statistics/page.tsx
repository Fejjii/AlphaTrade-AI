"use client";

import { useCallback, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type {
  ExecutionActor,
  JournalStatsGroupBy,
  JournalStatsParams,
  JournalTradeSource,
  JournalTradeStatsMetrics,
  MarketRegime,
  SampleConfidence,
  TradeRuleCompliance,
} from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

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
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function num(value: number | null, digits = 2): string {
  return value === null ? "—" : value.toFixed(digits);
}

function ConfidenceBadge({ confidence }: { confidence: SampleConfidence }) {
  return <StatusBadge label={confidence} tone={CONFIDENCE_TONE[confidence]} />;
}

function MetricsSummary({ metrics }: { metrics: JournalTradeStatsMetrics }) {
  return (
    <div className="grid gap-2 text-sm text-zinc-300 md:grid-cols-3">
      <p>
        Trades: {metrics.trade_count} (W {metrics.wins} / L {metrics.losses} / BE{" "}
        {metrics.breakeven})
      </p>
      <p>Win rate: {pct(metrics.win_rate)}</p>
      <p>
        Net PnL: {formatDecimal(metrics.net_pnl_total)} (PnL on {metrics.pnl_sample_count}{" "}
        trades)
      </p>
      <p>Expectancy: {formatDecimal(metrics.expectancy)}</p>
      <p>
        Avg R: {num(metrics.average_r)} ({metrics.r_sample_count} trades)
      </p>
      <p>Profit factor: {num(metrics.profit_factor)}</p>
      <p>Avg winner: {formatDecimal(metrics.average_winner)}</p>
      <p>Avg loser: {formatDecimal(metrics.average_loser)}</p>
      <p>
        Costs: {formatDecimal(metrics.total_costs)} (fees {formatDecimal(metrics.fees_total)},
        funding {formatDecimal(metrics.funding_total)}, slippage{" "}
        {formatDecimal(metrics.slippage_total)})
      </p>
      <p>
        Avg MFE: {formatDecimal(metrics.average_mfe_amount)} ({metrics.mfe_sample_count} trades)
      </p>
      <p>
        Avg MAE: {formatDecimal(metrics.average_mae_amount)} ({metrics.mae_sample_count} trades)
      </p>
      <p>
        Realized vs available:{" "}
        {metrics.average_realized_vs_available_pct === null
          ? "—"
          : `${metrics.average_realized_vs_available_pct.toFixed(1)}%`}{" "}
        ({metrics.capture_sample_count} trades)
      </p>
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
  }, [groupBy, source, symbol, timeframe, regime, compliance, actor, dateFrom, dateTo, offset]);
  const { data, loading, error, reload } = useAsyncData(loader, [loader]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Journal statistics</h1>
        <p className="text-sm text-zinc-400">
          Deterministic aggregates over closed canonical journal trades (paper only). Metrics use
          recorded values only; small samples carry explicit confidence warnings.
        </p>
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          <div className="space-y-2">
            <Label htmlFor="stats-group-by">Group by</Label>
            <select
              id="stats-group-by"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
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
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="stats-source">Source</Label>
            <select
              id="stats-source"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
              value={source}
              onChange={(e) => {
                setSource(e.target.value as JournalTradeSource | "");
                setOffset(0);
              }}
            >
              <option value="">All sources</option>
              {SOURCE_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
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
          <div className="space-y-2">
            <Label htmlFor="stats-regime">Market regime</Label>
            <select
              id="stats-regime"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
              value={regime}
              onChange={(e) => {
                setRegime(e.target.value as MarketRegime | "");
                setOffset(0);
              }}
            >
              <option value="">All regimes</option>
              {REGIME_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="stats-compliance">Rule compliance</Label>
            <select
              id="stats-compliance"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
              value={compliance}
              onChange={(e) => {
                setCompliance(e.target.value as TradeRuleCompliance | "");
                setOffset(0);
              }}
            >
              <option value="">All trades</option>
              {COMPLIANCE_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="stats-actor">Execution</Label>
            <select
              id="stats-actor"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
              value={actor}
              onChange={(e) => {
                setActor(e.target.value as ExecutionActor | "");
                setOffset(0);
              }}
            >
              <option value="">Human + system</option>
              <option value="human">Human</option>
              <option value="system">System</option>
            </select>
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
      </div>

      {loading ? <LoadingState label="Loading journal statistics…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data ? (
        <>
          {data.truncated ? (
            <p className="rounded-md border border-amber-800 bg-amber-950/40 p-3 text-sm text-amber-300">
              Result capped at {data.max_rows} closed trades — aggregates are partial. Narrow the
              date range or filters.
            </p>
          ) : null}

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Overall (filtered)</CardTitle>
              <ConfidenceBadge confidence={data.overall.confidence} />
            </CardHeader>
            <CardContent className="space-y-3">
              <MetricsSummary metrics={data.overall} />
              {data.overall.warnings.length ? (
                <ul className="list-disc pl-5 text-xs text-amber-300">
                  {data.overall.warnings.map((w) => (
                    <li key={w.code}>{w.message}</li>
                  ))}
                </ul>
              ) : null}
            </CardContent>
          </Card>

          {data.group_by !== "overall" ? (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-medium">
                  {GROUP_BY_OPTIONS.find((o) => o.value === data.group_by)?.label} breakdown (
                  {data.total_buckets} groups)
                </h2>
                {data.total_buckets > BUCKET_PAGE_SIZE ? (
                  <div className="flex items-center gap-2 text-sm text-zinc-400">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - BUCKET_PAGE_SIZE))}
                    >
                      Previous
                    </Button>
                    <span>
                      {offset + 1}–{Math.min(offset + BUCKET_PAGE_SIZE, data.total_buckets)}
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
                      <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle className="text-base">{bucket.label}</CardTitle>
                        <ConfidenceBadge confidence={bucket.metrics.confidence} />
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <MetricsSummary metrics={bucket.metrics} />
                        {bucket.metrics.warnings.length ? (
                          <ul className="list-disc pl-5 text-xs text-amber-300">
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
    </div>
  );
}
