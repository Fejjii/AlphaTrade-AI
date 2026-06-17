"use client";

import type {
  PaperAlert,
  PaperEligibilityReport,
  PaperRuntimeHistoryRecord,
  PaperSchedulerStatus,
  PaperSignalResult,
  PaperTradeRecord,
  PaperValidationRun,
  PaperValidationSummary,
} from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Props = {
  summary: PaperValidationSummary | null;
  eligibility: PaperEligibilityReport | null;
  scheduler: PaperSchedulerStatus | null;
  history: PaperRuntimeHistoryRecord[];
  alerts: PaperAlert[];
  busy: boolean;
  signals: PaperSignalResult[];
  trades: PaperTradeRecord[];
  onStart: () => void;
  onScan: () => void;
  onTick: () => void;
  onStop: () => void;
  onSchedulerTick: () => void;
  onMarkAlertRead: (id: string) => void;
};

export function PaperValidationPanel({
  summary,
  eligibility,
  scheduler,
  history,
  alerts,
  busy,
  signals,
  trades,
  onStart,
  onScan,
  onTick,
  onStop,
  onSchedulerTick,
  onMarkAlertRead,
}: Props) {
  const latest: PaperValidationRun | undefined = summary?.runs[0];
  const openTrades = trades.filter((t) => t.status === "open");
  const closedTrades = trades.filter((t) => t.status === "closed");
  const dataStale = history.some((h) => h.data_freshness === "stale" || h.warnings.length > 0);
  const providerFallback = history.some((h) =>
    h.warnings.some((w) => w.toLowerCase().includes("fallback")),
  );

  return (
    <Card data-testid="paper-validation-panel">
      <CardHeader>
        <CardTitle className="text-base">Paper validation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p className="text-zinc-400" data-testid="paper-only-disclaimer">
          Simulated paper trades only — no exchange orders. Real trading disabled.
        </p>

        {scheduler ? (
          <div className="rounded border border-zinc-800 p-3" data-testid="scheduler-status">
            <p>
              Scheduler: env {scheduler.env_enabled ? "on" : "off"} · tenant{" "}
              {scheduler.tenant_enabled ? "on" : "off"} · effective{" "}
              {scheduler.effective_enabled ? "on" : "off"}
            </p>
            {scheduler.last_tick_at ? (
              <p data-testid="last-scheduler-tick">
                Last tick: {new Date(scheduler.last_tick_at).toLocaleString()} (
                {scheduler.last_tick_status ?? "—"})
              </p>
            ) : (
              <p data-testid="last-scheduler-tick">Last tick: none yet</p>
            )}
            <Button
              variant="secondary"
              size="sm"
              className="mt-2"
              disabled={busy}
              onClick={onSchedulerTick}
              data-testid="manual-scheduler-tick"
            >
              Manual scheduler tick
            </Button>
          </div>
        ) : null}

        {latest ? (
          <p data-testid="paper-validation-run-status">
            Run status: <span className="text-zinc-100">{latest.status}</span> · Mode:{" "}
            <span data-testid="runtime-mode">{latest.runtime_mode ?? "scan_only"}</span>
          </p>
        ) : null}

        {eligibility ? (
          <div className="space-y-2 rounded border border-zinc-800 p-3" data-testid="paper-eligibility-status">
            <p>
              Status: <span className="text-zinc-100">{eligibility.status}</span> · Paper eligible:{" "}
              {eligibility.paper_eligible ? "yes" : "no"}
            </p>
            <p>Recommendation: {eligibility.recommendation}</p>
            {eligibility.blockers.length > 0 ? (
              <ul className="list-disc pl-4 text-amber-200" data-testid="paper-eligibility-blockers">
                {eligibility.blockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {latest && (latest.blockers?.length ?? 0) > 0 ? (
          <ul className="list-disc pl-4 text-amber-200" data-testid="paper-validation-blockers">
            {(latest.blockers ?? []).map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        ) : null}

        {dataStale ? (
          <p className="text-amber-200" data-testid="data-freshness-warning">
            Data freshness warning — recent cycles reported stale or limited data.
          </p>
        ) : null}

        {providerFallback ? (
          <p className="text-amber-200" data-testid="provider-fallback-warning">
            Provider fallback was used in a recent runtime cycle.
          </p>
        ) : null}

        {eligibility && eligibility.unresolved_lesson_candidates.length > 0 ? (
          <p className="text-amber-200" data-testid="unresolved-lesson-blocker">
            {eligibility.unresolved_lesson_candidates.length} unresolved lesson candidate(s) —
            review in Lessons before paper promotion.
          </p>
        ) : null}

        {latest?.last_scan_result ? (
          <div className="rounded border border-zinc-800 p-3" data-testid="latest-scan-result">
            <p className="text-zinc-400">Latest scan</p>
            <pre className="overflow-x-auto text-xs text-zinc-400">
              {JSON.stringify(latest.last_scan_result, null, 0)}
            </pre>
          </div>
        ) : null}

        {history.length > 0 ? (
          <div data-testid="runtime-history">
            <p className="text-zinc-400">Runtime cycles ({history.length})</p>
            <ul className="space-y-1 text-xs">
              {history.slice(0, 5).map((h) => (
                <li key={h.id} className="rounded border border-zinc-800 px-2 py-1">
                  {h.mode} · {h.status}
                  {h.reason ? ` — ${h.reason}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {alerts.length > 0 ? (
          <div data-testid="paper-validation-alerts">
            <p className="text-zinc-400">Recent alerts ({alerts.length})</p>
            <ul className="space-y-1">
              {alerts.slice(0, 5).map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-2 rounded border border-zinc-800 px-2 py-1">
                  <span className={a.read_at ? "text-zinc-500" : "text-zinc-100"}>
                    [{a.severity}] {a.alert_type}: {a.message}
                  </span>
                  {!a.read_at ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => onMarkAlertRead(a.id)}
                      data-testid={`mark-alert-read-${a.id}`}
                    >
                      Mark read
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy} onClick={onStart} data-testid="start-paper-validation">
            {busy ? "Working…" : "Start paper validation"}
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !latest}
            onClick={onScan}
            data-testid="scan-paper-validation"
          >
            Run scan
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !latest}
            onClick={onTick}
            data-testid="tick-paper-validation"
          >
            Run tick
          </Button>
          <Button
            variant="outline"
            disabled={busy || !latest}
            onClick={onStop}
            data-testid="stop-paper-validation"
          >
            Stop
          </Button>
        </div>

        {signals.length > 0 ? (
          <ul className="space-y-1" data-testid="paper-signals-list">
            <p className="text-zinc-400">Paper signals ({signals.length})</p>
            {signals.slice(0, 5).map((s) => (
              <li key={s.id} className="rounded border border-zinc-800 px-2 py-1">
                {s.triggered ? "Triggered" : "No setup"} · {s.status} · conf{" "}
                {(s.confidence * 100).toFixed(0)}%
              </li>
            ))}
          </ul>
        ) : null}

        {openTrades.length > 0 ? (
          <div data-testid="open-paper-positions">
            <p className="text-zinc-400">Open positions ({openTrades.length})</p>
            <ul className="space-y-1">
              {openTrades.map((t) => (
                <li key={t.id}>
                  {t.direction} {t.symbol} @ {t.entry_price}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {closedTrades.length > 0 ? (
          <table className="w-full text-left text-xs" data-testid="paper-trades-table">
            <thead>
              <tr className="text-zinc-500">
                <th className="py-1">Symbol</th>
                <th>PnL</th>
                <th>Exit</th>
              </tr>
            </thead>
            <tbody>
              {closedTrades.slice(0, 8).map((t) => (
                <tr key={t.id} className="border-t border-zinc-800">
                  <td className="py-1">{t.symbol}</td>
                  <td>{t.net_pnl ?? "—"}</td>
                  <td>{t.exit_reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}

        {latest?.metrics ? (
          <ul className="grid gap-1 sm:grid-cols-2" data-testid="paper-validation-metrics">
            <li>Paper trades: {latest.metrics.paper_trades_count}</li>
            <li>Win rate: {(latest.metrics.win_rate * 100).toFixed(1)}%</li>
            <li>Net PnL: {latest.metrics.net_pnl}</li>
            <li>Profit factor: {latest.metrics.profit_factor?.toFixed(2)}</li>
            <li data-testid="max-drawdown-metric">
              Max DD: {latest.metrics.max_drawdown_pct.toFixed(1)}%
            </li>
            <li>Run recommendation: {latest.recommendation ?? "—"}</li>
          </ul>
        ) : (
          <p className="text-zinc-500">
            Metrics update as paper trades close — run scan and tick to simulate.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
