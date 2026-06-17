"use client";

import { useCallback, useState } from "react";

import { ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { NotificationPreferences } from "@/lib/api/types";

function providerLabel(status: string): string {
  switch (status) {
    case "configured":
      return "Configured";
    case "not_configured":
      return "Not configured";
    case "disabled":
      return "Disabled";
    case "user_disabled":
      return "Off in preferences";
    default:
      return status;
  }
}

export function NotificationSettingsPanel() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loader = useCallback(() => api.notifications.preferences(), []);
  const statusLoader = useCallback(() => api.alerts.deliveryStatus(), []);
  const { data: prefs, loading, error, reload } = useAsyncData(loader, []);
  const { data: deliveryStatus } = useAsyncData(statusLoader, []);

  async function save(patch: Partial<NotificationPreferences>) {
    setBusy(true);
    setMessage(null);
    try {
      await api.notifications.updatePreferences(patch);
      await reload();
      setMessage("Preferences saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.notifications.sendTest();
      setMessage(result.message);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Test failed.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!prefs) return null;

  const channelStatuses = deliveryStatus?.channel_statuses ?? [];

  return (
    <Card data-testid="notification-settings-panel">
      <CardHeader>
        <CardTitle>Notifications</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        <p className="text-zinc-400" data-testid="notifications-never-trade-copy">
          Alerts notify you about paper validation events. Alerts never execute trades.
        </p>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>In-app alerts</span>
          <Badge variant="success" data-testid="in-app-enabled-badge">
            {prefs.in_app_enabled ? "Enabled" : "Disabled"}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>Webhook delivery</span>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={prefs.webhook_enabled}
              disabled={busy}
              onChange={(e) => void save({ webhook_enabled: e.target.checked })}
              data-testid="webhook-toggle"
            />
            <span>{prefs.webhook_enabled ? "On" : "Off"}</span>
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>Telegram delivery</span>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={prefs.telegram_enabled}
              disabled={busy}
              onChange={(e) => void save({ telegram_enabled: e.target.checked })}
              data-testid="telegram-toggle"
            />
            <span>{prefs.telegram_enabled ? "On" : "Off"}</span>
          </label>
        </div>

        <div className="space-y-1" data-testid="provider-status-list">
          {channelStatuses.map((ch) => (
            <p key={ch.channel} className="text-xs text-zinc-500" data-testid={`provider-${ch.channel}`}>
              {ch.channel}: {providerLabel(ch.status_label)}
            </p>
          ))}
          {channelStatuses.length === 0 ? (
            <p className="text-xs text-zinc-500" data-testid="provider-disabled-status">
              External providers disabled by default.
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="text-zinc-400">Minimum severity</label>
          <select
            className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1"
            value={prefs.min_severity}
            disabled={busy}
            onChange={(e) => void save({ min_severity: e.target.value })}
            data-testid="min-severity-select"
          >
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        <Button
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={() => void sendTest()}
          data-testid="send-test-notification"
        >
          Send test notification
        </Button>

        {message ? (
          <p className="text-xs text-zinc-400" data-testid="notification-action-message">
            {message}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
