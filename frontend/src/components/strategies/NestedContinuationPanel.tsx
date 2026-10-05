"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { displayedBrainSetup, useBrainSetupClock } from "@/hooks/useBrainSetupClock";
import { useAsyncData } from "@/hooks/useAsyncData";

const EMPTY_SETUPS: never[] = [];

export function NestedContinuationPanel() {
  const loader = useCallback(() => api.strategyBrain.overview(), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);
  const now = useBrainSetupClock(data?.setups ?? EMPTY_SETUPS);
  const [symbol, setSymbol] = useState("");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [timeframe, setTimeframe] = useState("15m");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const mutate = async (action: () => Promise<unknown>) => {
    setBusy(true); setMessage(null);
    try { await action(); await reload(); }
    catch (failure) { setMessage(failure instanceof Error ? failure.message : "Strategy action failed"); }
    finally { setBusy(false); }
  };
  return <Card className="mb-6">
    <CardHeader><CardTitle>Nested Continuation</CardTitle>
      <p className="text-sm text-text-muted">Operational structure proxy · paper only · provisional research rules</p>
    </CardHeader>
    <CardContent className="space-y-4">
      {loading && !data && <p>Loading stored setups…</p>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="alert">{message}</p>}
      {data && <>
        <Button variant="secondary" disabled={loading || busy} onClick={() => void reload()}>Refresh stored setups</Button>
        <p className="text-sm">Watcher markets: {data.watched_symbols.join(", ") || "none enabled"}</p>
        <div className="flex flex-wrap items-center gap-3">
          <label>Market <select aria-label="Nested market" value={symbol || data.watched_symbols[0] || ""} onChange={e => setSymbol(e.target.value)} className="bg-surface">
            {data.watched_symbols.map(value => <option key={value}>{value}</option>)}
          </select></label>
          <label>Direction <select aria-label="Nested direction" value={direction} onChange={e => setDirection(e.target.value as "long" | "short")} className="bg-surface">
            <option value="long">Bullish proxy</option><option value="short">Bearish mirror</option>
          </select></label>
          <label>Timeframe <select aria-label="Nested timeframe" value={timeframe} onChange={e => setTimeframe(e.target.value)} className="bg-surface">
            <option value="15m">15m</option><option value="30m">30m</option><option value="1h">1h</option>
          </select></label>
          <Button disabled={busy || !data.watched_symbols.length} onClick={() => void mutate(() => api.strategyBrain.createNested({symbol: symbol || data.watched_symbols[0]!, direction, trigger_timeframe: timeframe}))}>Create research draft</Button>
        </div>
        {data.strategies.map(strategy => <div key={strategy.version_id} className="space-y-2 rounded border border-border p-3">
          <h3>{strategy.name} · version {strategy.version} · {strategy.status}</h3>
          <p className="text-sm">{strategy.spec.symbol} · {strategy.spec.trigger_timeframe} · {strategy.spec.direction}. Insufficient history for expectancy.</p>
          <details><summary>Review versioned rules</summary><pre className="overflow-x-auto whitespace-pre-wrap text-xs">{JSON.stringify(strategy.spec.parameters, null, 2)}</pre>
            <p className="text-sm">Closed impulse break after a controlled pullback; stop at the pullback extreme; measured impulse target. Existing risk and paper execution gates remain required.</p>
          </details>
          {!["approved", "active", "paused", "retired"].includes(strategy.status) && <Button disabled={busy} variant="secondary" onClick={() => void mutate(async () => {
            const result = await api.strategies.compileVersion(strategy.strategy_id, strategy.version_id);
            if (result.status !== "executable") throw new Error(result.failures.map(f => f.message).join("; ") || "Rules did not compile");
            await api.strategies.approveVersion(strategy.strategy_id, strategy.version_id, {confirm: "I confirm"});
          })}>Approve these paper rules</Button>}
          <Link href={`/strategy-lab/${strategy.strategy_id}`} className="ml-3 text-sm underline">Strategy details</Link>
        </div>)}
        {!data.setups.length && <p>No stored Nested setups yet. The existing Watcher must scan an approved version.</p>}
        <ul className="space-y-3">{data.setups.map(stored => { const setup = displayedBrainSetup(stored, now); return <li key={setup.setup_id} className="rounded border border-border p-3">
          <Link href={`/strategies/setups/${setup.setup_id}`} className="font-medium underline">{setup.symbol || setup.instrument} · {setup.stage} · {setup.state}</Link>
          <p className="text-sm">{setup.direction} · evidence {setup.freshness} · risk {setup.risk_state} · {new Date(setup.observed_at).toLocaleString()}</p>
          <p className="text-sm">{setup.reason_codes.join(", ")}</p>
        </li>; })}</ul>
        <p className="text-xs text-text-muted">Stage describes structure, not profitability. CVD, order flow, open interest and funding are unsupported.</p>
      </>}
    </CardContent>
  </Card>;
}
