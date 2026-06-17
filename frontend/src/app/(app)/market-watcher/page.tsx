"use client";

import { useCallback, useState } from "react";

import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function MarketWatcherPage() {
  const [busy, setBusy] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [bridgeResult, setBridgeResult] = useState<string | null>(null);

  const { data: status, loading, error, reload } = useAsyncData(
    () => api.marketWatcher.status(),
    [],
  );
  const bridgeLoader = useCallback(() => api.marketWatcher.bridgeStatus(), []);
  const observationsLoader = useCallback(() => api.marketWatcher.observations({ limit: 10 }), []);
  const historyLoader = useCallback(() => api.marketWatcher.bridgeHistory({ limit: 20 }), []);

  const { data: bridgeStatus, reload: reloadBridge } = useAsyncData(bridgeLoader, []);
  const { data: observations, reload: reloadObservations } = useAsyncData(observationsLoader, []);
  const { data: bridgeHistory, reload: reloadHistory } = useAsyncData(historyLoader, []);

  async function runScan() {
    setBusy(true);
    setScanResult(null);
    try {
      const result = await api.marketWatcher.scan();
      setScanResult(
        result.effective_enabled
          ? `Scanned ${result.symbols_scanned} symbol(s), ${result.observations_created} observation(s).`
          : result.decisions.join(" ") || "Market watcher is disabled.",
      );
      await Promise.all([reload(), reloadObservations()]);
    } catch (err) {
      setScanResult(err instanceof Error ? err.message : "Scan failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runBridgeTick() {
    setBusy(true);
    setBridgeResult(null);
    try {
      const result = await api.marketWatcher.bridgeTick();
      setBridgeResult(
        result.effective_enabled
          ? `Bridge tick: ${result.scans_triggered} scan(s) triggered from ${result.observations_processed} observation(s).`
          : result.decisions.join(" ") || "Bridge is disabled.",
      );
      await Promise.all([reloadBridge(), reloadHistory()]);
    } catch (err) {
      setBridgeResult(err instanceof Error ? err.message : "Bridge tick failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Market Watcher</h1>
        <p className="text-sm text-zinc-400" data-testid="market-watcher-readonly-copy">
          Read-only market scanning for paper validation prep. No orders are placed.
        </p>
        <p className="text-sm text-zinc-500" data-testid="market-watcher-paper-only">
          Paper only — no broker or exchange execution.
        </p>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {status ? (
        <section
          className="rounded-lg border border-zinc-800 p-4 text-sm"
          data-testid="market-watcher-status"
        >
          <h2 className="mb-2 font-medium">Watcher status</h2>
          <p>
            Env enabled:{" "}
            <span data-testid="market-watcher-env-enabled">{String(status.env_enabled)}</span>
          </p>
          <p>
            Effective:{" "}
            <span data-testid="market-watcher-effective">{String(status.effective_enabled)}</span>
          </p>
          <p data-testid="market-watcher-symbols">
            Watched symbols: {status.watched_symbols.join(", ") || "none (using defaults when enabled)"}
          </p>
          {!status.env_enabled ? (
            <p className="mt-2 text-zinc-500" data-testid="market-watcher-disabled-state">
              MARKET_WATCHER_ENABLED=false — manual scan returns a disabled result.
            </p>
          ) : null}
        </section>
      ) : null}

      {bridgeStatus ? (
        <section
          className="rounded-lg border border-zinc-800 p-4 text-sm"
          data-testid="market-watcher-bridge-status"
        >
          <h2 className="mb-2 font-medium">Bridge status</h2>
          <p data-testid="bridge-env-enabled">Env enabled: {String(bridgeStatus.env_enabled)}</p>
          <p data-testid="bridge-effective-enabled">
            Effective: {String(bridgeStatus.effective_enabled)}
          </p>
          <p>Auto tick: {String(bridgeStatus.auto_tick_enabled)}</p>
          {bridgeStatus.last_tick_at ? (
            <p>Last tick: {new Date(bridgeStatus.last_tick_at).toLocaleString()}</p>
          ) : null}
          {!bridgeStatus.env_enabled ? (
            <p className="mt-2 text-zinc-500" data-testid="bridge-disabled-state">
              MARKET_WATCHER_BRIDGE_ENABLED=false — bridge tick returns a disabled result.
            </p>
          ) : null}
        </section>
      ) : null}

      {observations && observations.items.length > 0 ? (
        <section className="rounded-lg border border-zinc-800 p-4 text-sm" data-testid="market-watcher-observations">
          <h2 className="mb-2 font-medium">Latest observations</h2>
          <ul className="space-y-1">
            {observations.items.slice(0, 5).map((obs) => (
              <li key={obs.id} data-testid="market-watcher-observation-row">
                {obs.symbol} — {obs.status} ({obs.data_freshness ?? "unknown"})
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {bridgeHistory && bridgeHistory.items.length > 0 ? (
        <section className="rounded-lg border border-zinc-800 p-4 text-sm" data-testid="bridge-decision-history">
          <h2 className="mb-2 font-medium">Bridge decisions</h2>
          <ul className="space-y-2">
            {bridgeHistory.items.slice(0, 10).map((d) => (
              <li key={d.id} data-testid="bridge-decision-row">
                <span className="font-mono text-xs text-zinc-500">{d.decision}</span>
                {d.symbol ? ` · ${d.symbol}` : null}
                {d.reason ? (
                  <p className="text-zinc-400" data-testid="bridge-skipped-reason">
                    {d.reason}
                  </p>
                ) : null}
                {d.triggered_scan_id ? (
                  <p className="text-zinc-500">Triggered scan: {d.triggered_scan_id}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button
          disabled={busy}
          onClick={() => void runScan()}
          data-testid="market-watcher-scan-button"
        >
          Run read-only scan
        </Button>
        {bridgeStatus?.env_enabled ? (
          <Button
            disabled={busy}
            variant="secondary"
            onClick={() => void runBridgeTick()}
            data-testid="market-watcher-bridge-tick-button"
          >
            Run bridge tick
          </Button>
        ) : null}
      </div>

      {scanResult ? (
        <p className="text-sm text-zinc-400" data-testid="market-watcher-scan-result">
          {scanResult}
        </p>
      ) : null}
      {bridgeResult ? (
        <p className="text-sm text-zinc-400" data-testid="market-watcher-bridge-result">
          {bridgeResult}
        </p>
      ) : null}
    </div>
  );
}
