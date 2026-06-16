"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { BacktestRun, PaginatedBacktestTrades } from "@/lib/api/types";

type Props = {
  strategyId: string;
  onRun: (assumptions: Record<string, unknown>) => Promise<BacktestRun>;
  onLoadTrades: (runId: string) => Promise<PaginatedBacktestTrades>;
  latestRun?: BacktestRun | null;
};

export function BacktestPanel({ strategyId, onRun, onLoadTrades, latestRun }: Props) {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("4h");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-06-01");
  const [capital, setCapital] = useState("10000");
  const [feesBps, setFeesBps] = useState("4");
  const [slippageBps, setSlippageBps] = useState("5");
  const [riskPct, setRiskPct] = useState("1");
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<BacktestRun | null>(latestRun ?? null);
  const [trades, setTrades] = useState<PaginatedBacktestTrades | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const result = await onRun({
        symbol,
        exchange: "mock",
        timeframe,
        start_date: startDate,
        end_date: endDate,
        initial_capital: Number(capital),
        fees_bps: Number(feesBps),
        slippage_bps: Number(slippageBps),
        risk_per_trade_pct: Number(riskPct),
      });
      setRun(result);
      if (result.id) {
        const listing = await onLoadTrades(result.id);
        setTrades(listing);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setBusy(false);
    }
  }

  const metrics = run?.result?.metrics;
  const limitations = run?.result?.limitations ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Backtest v1 (historical simulation)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        <p className="text-zinc-400">
          Paper-only historical replay with fees and slippage. Not a profit guarantee. Real trading
          remains disabled.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1">
            <span className="text-zinc-400">Symbol</span>
            <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-zinc-400">Timeframe</span>
            <Input value={timeframe} onChange={(e) => setTimeframe(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-zinc-400">Start date</span>
            <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-zinc-400">End date</span>
            <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-zinc-400">Initial capital</span>
            <Input value={capital} onChange={(e) => setCapital(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-zinc-400">Risk % / trade</span>
            <Input value={riskPct} onChange={(e) => setRiskPct(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-zinc-400">Fees (bps)</span>
            <Input value={feesBps} onChange={(e) => setFeesBps(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-zinc-400">Slippage (bps)</span>
            <Input value={slippageBps} onChange={(e) => setSlippageBps(e.target.value)} />
          </label>
        </div>
        <Button disabled={busy} onClick={() => void handleRun()}>
          {busy ? "Running…" : "Run backtest"}
        </Button>
        {error ? <p className="text-red-400">{error}</p> : null}
        {run?.result ? (
          <div className="space-y-2 rounded-lg border border-zinc-800 p-3">
            <p>
              Status: {run.status} · Recommendation:{" "}
              <span className="text-amber-300">{run.result.recommendation}</span>
            </p>
            {metrics ? (
              <ul className="grid gap-1 sm:grid-cols-2">
                <li>Trades: {metrics.trade_count}</li>
                <li>Win rate: {(metrics.win_rate * 100).toFixed(1)}%</li>
                <li>Profit factor: {metrics.profit_factor?.toFixed(2)}</li>
                <li>Max DD: {metrics.max_drawdown_pct?.toFixed(1)}%</li>
                <li>Net PnL: {metrics.net_pnl}</li>
                <li>Return: {metrics.return_pct?.toFixed(2)}%</li>
              </ul>
            ) : null}
            {limitations.length ? (
              <p className="text-amber-400">Limitations: {limitations.join(" ")}</p>
            ) : null}
            <p className="text-xs text-zinc-500">{run.result.note}</p>
          </div>
        ) : null}
        {trades?.items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-zinc-400">
                  <th className="p-1">Entry</th>
                  <th className="p-1">Exit</th>
                  <th className="p-1">Net PnL</th>
                  <th className="p-1">Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.items.slice(0, 10).map((t) => (
                  <tr key={`${t.entry_time}-${t.exit_time}`} className="border-t border-zinc-800">
                    <td className="p-1">{t.entry_price}</td>
                    <td className="p-1">{t.exit_price}</td>
                    <td className="p-1">{t.net_pnl}</td>
                    <td className="p-1">{t.exit_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <p className="text-xs text-zinc-500">Strategy ID: {strategyId}</p>
      </CardContent>
    </Card>
  );
}
