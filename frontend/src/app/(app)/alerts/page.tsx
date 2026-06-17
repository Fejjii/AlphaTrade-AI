"use client";

import { useCallback, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { PaperAlert } from "@/lib/api/types";

export default function AlertsPage() {
  const [filterType, setFilterType] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  const [busy, setBusy] = useState(false);

  const loader = useCallback(
    () =>
      api.alerts.list({
        alert_type: filterType || undefined,
        severity: filterSeverity || undefined,
        limit: 50,
      }),
    [filterType, filterSeverity],
  );
  const summaryLoader = useCallback(() => api.alerts.summary(), []);
  const { data, loading, error, reload } = useAsyncData(loader, [filterType, filterSeverity]);
  const { data: summary, reload: reloadSummary } = useAsyncData(summaryLoader, []);

  async function markRead(alert: PaperAlert) {
    setBusy(true);
    try {
      await api.alerts.markRead(alert.id);
      await Promise.all([reload(), reloadSummary()]);
    } finally {
      setBusy(false);
    }
  }

  async function markAllRead() {
    setBusy(true);
    try {
      await api.alerts.markAllRead();
      await Promise.all([reload(), reloadSummary()]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Alerts</h1>
          <p className="text-sm text-zinc-400">
            Paper validation alerts — storage only, no Telegram or email delivery yet.
          </p>
          {summary ? (
            <p className="mt-1 text-sm text-zinc-300" data-testid="alerts-unread-count">
              {summary.unread} unread of {summary.total}
            </p>
          ) : null}
        </div>
        <Button variant="secondary" disabled={busy} onClick={() => void markAllRead()}>
          Mark all read
        </Button>
      </div>

      <div className="flex flex-wrap gap-2 text-sm">
        <select
          className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          data-testid="alert-type-filter"
        >
          <option value="">All types</option>
          <option value="setup_signal_detected">Setup signal</option>
          <option value="paper_trade_opened">Trade opened</option>
          <option value="paper_trade_closed">Trade closed</option>
          <option value="data_stale">Data stale</option>
          <option value="strategy_blocked">Strategy blocked</option>
        </select>
        <select
          className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          data-testid="alert-severity-filter"
        >
          <option value="">All severities</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      <div className="grid gap-3" data-testid="alerts-list">
        {data?.items.length ? (
          data.items.map((alert) => (
            <article
              key={alert.id}
              className="rounded-lg border border-zinc-800 p-4 text-sm"
              data-testid="alert-card"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-zinc-100">{alert.alert_type}</span>
                <span className="text-zinc-500">{new Date(alert.created_at).toLocaleString()}</span>
              </div>
              <p className="mt-1 text-zinc-300">{alert.message}</p>
              <p className="mt-1 text-xs text-zinc-500">
                Severity: {alert.severity}
                {alert.strategy_id ? ` · Strategy ${alert.strategy_id.slice(0, 8)}` : ""}
                {alert.paper_validation_run_id
                  ? ` · Run ${alert.paper_validation_run_id.slice(0, 8)}`
                  : ""}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {alert.read_at ? "Read" : "Unread"}
              </p>
              {!alert.read_at ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  disabled={busy}
                  onClick={() => void markRead(alert)}
                  data-testid="mark-alert-read"
                >
                  Mark read
                </Button>
              ) : null}
            </article>
          ))
        ) : (
          <EmptyState title="No alerts" />
        )}
      </div>
    </div>
  );
}
