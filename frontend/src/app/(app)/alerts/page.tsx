"use client";

import { useCallback, useState } from "react";

import { AlertRoutingCard } from "@/components/AlertRoutingCard";
import { TelegramTestPanel } from "@/components/TelegramTestPanel";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import {
  alertNextAction,
  alertSourceLabel,
  alertTypeLabel,
  severityRank,
  severityVariant,
} from "@/lib/alert-display";
import type { PaperAlert } from "@/lib/api/types";

export default function AlertsPage() {
  const [filterType, setFilterType] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

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
  const routingLoader = useCallback(() => api.alerts.routingSummary(), []);
  const deliveryLoader = useCallback(() => api.alerts.deliveryStatus(), []);
  const { data, loading, error, reload } = useAsyncData(loader, [filterType, filterSeverity]);
  const { data: summary, reload: reloadSummary } = useAsyncData(summaryLoader, []);
  const { data: routing } = useAsyncData(routingLoader, []);
  const { data: deliveryStatus } = useAsyncData(deliveryLoader, []);

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

  async function deliverAlert(alert: PaperAlert) {
    setBusy(true);
    setActionMessage(null);
    try {
      const result = await api.alerts.deliver(alert.id);
      setActionMessage(result.message);
      await reload();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Delivery failed.");
    } finally {
      setBusy(false);
    }
  }

  async function deliverPending() {
    setBusy(true);
    setActionMessage(null);
    try {
      const result = await api.alerts.deliverPending();
      setActionMessage(`Delivered ${result.delivered} of ${result.processed} pending alert(s).`);
      await reload();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Deliver pending failed.");
    } finally {
      setBusy(false);
    }
  }

  const externalEnabled = deliveryStatus?.effective_external_enabled ?? false;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Alerts</h1>
          <p className="text-sm text-zinc-400" data-testid="alerts-in-app-copy">
            In-app alerts are active. External delivery is disabled unless configured.
          </p>
          <p className="text-sm text-zinc-500" data-testid="alerts-paper-only-disclaimer">
            No real trades are executed from alerts. Paper validation only.
          </p>
          {summary ? (
            <p className="mt-1 text-sm text-zinc-300" data-testid="alerts-unread-count">
              {summary.unread} unread of {summary.total}
            </p>
          ) : null}
          {deliveryStatus ? (
            <div className="mt-1 space-y-1" data-testid="alerts-provider-status">
              <p className="text-xs text-zinc-500" data-testid="alerts-delivery-disabled-copy">
                External delivery:{" "}
                {deliveryStatus.effective_external_enabled ? "enabled" : "disabled by default"}
              </p>
              {deliveryStatus.channel_statuses?.map((ch) => (
                <p key={ch.channel} className="text-xs text-zinc-600">
                  {ch.channel}: {ch.status_label}
                </p>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {externalEnabled ? (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void deliverPending()}
              data-testid="deliver-pending-alerts"
            >
              Deliver pending
            </Button>
          ) : null}
          <Button variant="secondary" disabled={busy} onClick={() => void markAllRead()}>
            Mark all read
          </Button>
        </div>
      </div>

      {actionMessage ? (
        <p className="text-sm text-zinc-400" data-testid="alert-action-message">
          {actionMessage}
        </p>
      ) : null}

      {routing ? <AlertRoutingCard routing={routing} /> : null}
      {routing ? <TelegramTestPanel routing={routing} /> : null}

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
          [...data.items]
            .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
            .map((alert) => (
            <article
              key={alert.id}
              className="rounded-lg border border-zinc-800 p-4 text-sm"
              data-testid="alert-card"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={severityVariant(alert.severity)} data-testid="alert-severity-badge">
                    {alert.severity}
                  </Badge>
                  <span className="font-medium text-zinc-100" data-testid="alert-type-label">
                    {alertTypeLabel(alert.alert_type)}
                  </span>
                </div>
                <span className="text-zinc-500">{new Date(alert.created_at).toLocaleString()}</span>
              </div>
              <p className="mt-1 text-zinc-300">{alert.message}</p>
              <p className="mt-1 text-xs text-zinc-500" data-testid="alert-source-label">
                Source: {alertSourceLabel(alert.alert_source)}
                {" · "}
                {alert.read_at ? "Read" : "Unread"}
              </p>
              <p className="mt-1 text-xs text-zinc-400" data-testid="alert-next-action">
                Suggested: {alertNextAction(alert.alert_type)}
              </p>
              <p className="mt-1 text-xs text-zinc-500" data-testid="alert-delivery-status">
                Delivery: {alert.delivery_channel ?? "in_app"} · {alert.delivery_status ?? "disabled"}
                {alert.delivered_at
                  ? ` · Delivered ${new Date(alert.delivered_at).toLocaleString()}`
                  : ""}
                {alert.delivery_attempts ? ` · Attempts ${alert.delivery_attempts}` : ""}
              </p>
              {alert.delivery_skipped_reason ? (
                <p className="mt-1 text-xs text-zinc-500" data-testid="alert-skipped-reason">
                  Skipped: {alert.delivery_skipped_reason}
                </p>
              ) : null}
              {alert.retry_exhausted ? (
                <p className="mt-1 text-xs text-amber-500/80" data-testid="alert-retry-exhausted">
                  Retry exhausted — alert remains in-app only.
                </p>
              ) : null}
              {alert.last_delivery_error ? (
                <p className="mt-1 text-xs text-amber-500/80" data-testid="alert-delivery-error">
                  Last error: {alert.last_delivery_error}
                </p>
              ) : null}
              {alert.strategy_id || alert.paper_validation_run_id ? (
                <details className="mt-1 text-xs text-zinc-500" data-testid="alert-technical-ids">
                  <summary className="cursor-pointer">Technical IDs</summary>
                  {alert.strategy_id ? <p>Strategy: {alert.strategy_id}</p> : null}
                  {alert.paper_validation_run_id ? (
                    <p>Run: {alert.paper_validation_run_id}</p>
                  ) : null}
                </details>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-2">
                {!alert.read_at ? (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => void markRead(alert)}
                    data-testid="mark-alert-read"
                  >
                    Mark read
                  </Button>
                ) : null}
                {externalEnabled && alert.delivery_status === "pending" ? (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => void deliverAlert(alert)}
                    data-testid="deliver-alert-button"
                  >
                    Deliver
                  </Button>
                ) : null}
              </div>
            </article>
          ))
        ) : (
          <EmptyState title="No alerts" />
        )}
      </div>
    </div>
  );
}
