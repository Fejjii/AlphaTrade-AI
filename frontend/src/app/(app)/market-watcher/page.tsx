"use client";

import { useState } from "react";

import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function MarketWatcherPage() {
  const [busy, setBusy] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const { data: status, loading, error, reload } = useAsyncData(() => api.marketWatcher.status(), []);

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
      await reload();
    } catch (err) {
      setScanResult(err instanceof Error ? err.message : "Scan failed.");
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

      <Button
        disabled={busy}
        onClick={() => void runScan()}
        data-testid="market-watcher-scan-button"
      >
        Run read-only scan
      </Button>

      {scanResult ? (
        <p className="text-sm text-zinc-400" data-testid="market-watcher-scan-result">
          {scanResult}
        </p>
      ) : null}
    </div>
  );
}
