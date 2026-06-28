"use client";

import { useCallback, useMemo, useState } from "react";

import { MarketWatcherScannerCard } from "@/components/MarketWatcherScannerCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { MarketWatcherScanResult } from "@/lib/api/types";

const CONFIRM_PHRASE = "RUN_READ_ONLY_SCAN";
const CREATE_IN_APP_ALERTS_PHRASE = "CREATE_IN_APP_ALERTS_ONLY";
const DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];
const DEFAULT_TIMEFRAMES = ["15m", "1h"];

export default function WatcherPage() {
  const [busy, setBusy] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [confirm, setConfirm] = useState("");
  const [createAlertsConfirm, setCreateAlertsConfirm] = useState("");
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(DEFAULT_SYMBOLS);
  const [selectedTimeframes, setSelectedTimeframes] = useState<string[]>(DEFAULT_TIMEFRAMES);
  const [scanResult, setScanResult] = useState<MarketWatcherScanResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  const summaryLoader = useCallback(() => api.marketWatcher.summary(), []);
  const { data: summary, loading, error, reload } = useAsyncData(summaryLoader, []);

  const confirmReady = confirm.trim() === CONFIRM_PHRASE;
  const createAlertsConfirmReady =
    dryRun || createAlertsConfirm.trim() === CREATE_IN_APP_ALERTS_PHRASE;
  const scanBlocked = summary?.readiness === "blocked" || !summary?.manual_scan_available;

  const toggleSymbol = useCallback((symbol: string) => {
    setSelectedSymbols((current) =>
      current.includes(symbol) ? current.filter((s) => s !== symbol) : [...current, symbol],
    );
  }, []);

  const toggleTimeframe = useCallback((timeframe: string) => {
    setSelectedTimeframes((current) =>
      current.includes(timeframe) ? current.filter((t) => t !== timeframe) : [...current, timeframe],
    );
  }, []);

  const candidateCount = useMemo(() => scanResult?.candidates.length ?? 0, [scanResult]);

  async function runScan() {
    if (!confirmReady || !createAlertsConfirmReady || scanBlocked) return;
    setBusy(true);
    setScanError(null);
    try {
      const result = await api.marketWatcher.scan({
        confirm: CONFIRM_PHRASE,
        create_in_app_alerts_confirm: dryRun ? undefined : CREATE_IN_APP_ALERTS_PHRASE,
        symbols: selectedSymbols,
        timeframes: selectedTimeframes,
        dry_run: dryRun,
      });
      setScanResult(result);
      await reload();
    } catch (err) {
      setScanError(err instanceof Error ? err.message : "Scan failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Market Watcher Scanner</h1>
        <p className="text-sm text-zinc-400" data-testid="watcher-readonly-copy">
          Read-only scanner for in-app candidate alerts. No orders, no Telegram, no worker
          automation.
        </p>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {summary ? <MarketWatcherScannerCard summary={summary} /> : null}

      {summary ? (
        <Card data-testid="watcher-scan-panel">
          <CardHeader>
            <CardTitle className="text-base">Manual scan</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2" data-testid="watcher-dry-run-toggle">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(event) => setDryRun(event.target.checked)}
                />
                Dry-run (preview candidates only)
              </label>
              <StatusBadge
                label={dryRun ? "dry-run default on" : "will create in-app alerts"}
                tone={dryRun ? "healthy" : "warn"}
              />
            </div>

            {!dryRun ? (
              <div
                className="rounded border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-200"
                data-testid="watcher-in-app-only-warning"
              >
                Create in-app alerts only. No Telegram. No orders. No worker automation.
              </div>
            ) : null}

            <div>
              <p className="mb-2 text-zinc-400">Symbols</p>
              <div className="flex flex-wrap gap-2" data-testid="watcher-symbol-selector">
                {(summary.symbols_supported.length ? summary.symbols_supported : DEFAULT_SYMBOLS).map(
                  (symbol) => (
                    <button
                      key={symbol}
                      type="button"
                      className={`rounded border px-2 py-1 text-xs ${
                        selectedSymbols.includes(symbol)
                          ? "border-sky-500 text-sky-300"
                          : "border-zinc-700 text-zinc-400"
                      }`}
                      onClick={() => toggleSymbol(symbol)}
                    >
                      {symbol}
                    </button>
                  ),
                )}
              </div>
            </div>

            <div>
              <p className="mb-2 text-zinc-400">Timeframes</p>
              <div className="flex flex-wrap gap-2" data-testid="watcher-timeframe-selector">
                {(summary.timeframes_supported.length
                  ? summary.timeframes_supported
                  : DEFAULT_TIMEFRAMES
                ).map((timeframe) => (
                  <button
                    key={timeframe}
                    type="button"
                    className={`rounded border px-2 py-1 text-xs ${
                      selectedTimeframes.includes(timeframe)
                        ? "border-sky-500 text-sky-300"
                        : "border-zinc-700 text-zinc-400"
                    }`}
                    onClick={() => toggleTimeframe(timeframe)}
                  >
                    {timeframe}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-zinc-400" htmlFor="watcher-confirm-input">
                Type <span className="font-mono text-zinc-200">{CONFIRM_PHRASE}</span> to run scan
              </label>
              <input
                id="watcher-confirm-input"
                data-testid="watcher-confirm-input"
                className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                placeholder={CONFIRM_PHRASE}
              />
            </div>

            {!dryRun ? (
              <div className="space-y-2">
                <label className="block text-zinc-400" htmlFor="watcher-create-alerts-confirm-input">
                  Type{" "}
                  <span className="font-mono text-zinc-200">{CREATE_IN_APP_ALERTS_PHRASE}</span> to
                  create in-app alerts only
                </label>
                <input
                  id="watcher-create-alerts-confirm-input"
                  data-testid="watcher-create-alerts-confirm-input"
                  className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
                  value={createAlertsConfirm}
                  onChange={(event) => setCreateAlertsConfirm(event.target.value)}
                  placeholder={CREATE_IN_APP_ALERTS_PHRASE}
                />
              </div>
            ) : null}

            <Button
              data-testid="watcher-run-scan-button"
              disabled={
                busy ||
                !confirmReady ||
                !createAlertsConfirmReady ||
                scanBlocked ||
                selectedSymbols.length === 0
              }
              onClick={() => void runScan()}
            >
              {dryRun ? "Preview candidates" : "Run scan and create in-app alerts"}
            </Button>

            {scanBlocked ? (
              <p className="text-xs text-amber-400" data-testid="watcher-blocked-state">
                Manual scan is blocked until paper-only safety gates pass.
              </p>
            ) : null}

            {scanError ? (
              <p className="text-xs text-red-300" data-testid="watcher-scan-error">
                {scanError}
              </p>
            ) : null}

            {scanResult ? (
              <div className="space-y-2 rounded border border-zinc-800 p-3" data-testid="watcher-scan-results">
                <p data-testid="watcher-scan-status">
                  Status: {scanResult.status} · Candidates: {candidateCount} · Alerts created:{" "}
                  {scanResult.alerts_created} · Deduped: {scanResult.alerts_deduped}
                </p>
                <ul className="space-y-2 text-xs text-zinc-400">
                  {scanResult.candidates.map((candidate) => (
                    <li key={`${candidate.symbol}-${candidate.timeframe}-${candidate.condition}`}>
                      <span className="text-zinc-200">
                        {candidate.symbol} {candidate.timeframe} · {candidate.condition}
                      </span>
                      {candidate.deduped ? " (deduped)" : null}
                      <p>{candidate.message}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
