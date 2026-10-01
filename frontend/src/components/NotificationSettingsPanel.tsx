"use client";

import { useCallback, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  SettingsReadout,
  SettingsUnavailable,
} from "@/components/settings/SettingsReadout";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type {
  NotificationPreferences,
  WatcherMonitoringSnapshot,
} from "@/lib/api/types";
import { formatReasonCode } from "@/lib/watcher-monitoring";

export function NotificationSettingsPanel({
  snapshot = null,
}: {
  snapshot?: WatcherMonitoringSnapshot | null;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const loader = useCallback(() => api.notifications.preferences(), []);
  const statusLoader = useCallback(() => api.alerts.deliveryStatus(), []);
  const { data: prefs, loading, error, reload } = useAsyncData(loader, []);
  const delivery = useAsyncData(statusLoader, []);
  const telegram = delivery.data?.channel_statuses?.find(
    (channel) => channel.channel === "telegram",
  );

  async function save(patch: Partial<NotificationPreferences>) {
    setBusy(true);
    setMessage(null);
    try {
      await api.notifications.updatePreferences(patch);
      await reload();
      setMessage("Preferences saved.");
    } catch {
      setMessage("Preferences could not be saved. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card data-testid="notification-settings-panel">
      <CardHeader>
        <p
          className="text-sm text-text-muted"
          data-testid="notifications-never-trade-copy"
        >
          Paper alerts keep you informed and never execute trades.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div
          className="flex flex-wrap items-center gap-2"
          data-testid="settings-telegram-state"
        >
          <span>Telegram delivery</span>
          <StatusBadge
            label={
              delivery.loading
                ? "Loading…"
                : delivery.error || !delivery.data
                  ? "Unavailable"
                  : telegram
                    ? formatReasonCode(telegram.status_label)
                    : delivery.data.telegram_enabled === false
                      ? "Disabled"
                      : "State unavailable"
            }
            tone={telegram?.available ? "healthy" : "muted"}
          />
        </div>
        <p className="text-xs text-text-muted">
          {telegram
            ? `Telegram configuration: ${telegram.configured ? "configured" : "not configured"}. `
            : ""}
          Connection is not verified by this API. Delivery controls are
          unavailable here.
        </p>
        {delivery.error ? (
          <SettingsUnavailable
            label="Telegram state"
            loading={false}
            onRetry={() => void delivery.reload()}
          />
        ) : null}
        {loading || error || !prefs ? (
          <SettingsUnavailable
            label="Alert preferences"
            loading={loading}
            onRetry={() => void reload()}
          />
        ) : (
          <>
            <SettingsReadout
              rows={[
                ["In-app alerts", prefs.in_app_enabled ? "On" : "Off"],
                ["Telegram preference", prefs.telegram_enabled ? "On" : "Off"],
                ["Webhook preference", prefs.webhook_enabled ? "On" : "Off"],
                [
                  "Alert types",
                  prefs.enabled_alert_types === undefined
                    ? "Unavailable"
                    : prefs.enabled_alert_types === null
                      ? "All alert types"
                      : prefs.enabled_alert_types.length
                        ? prefs.enabled_alert_types
                            .map(formatReasonCode)
                            .join(", ")
                        : "None selected",
                ],
                [
                  "Quiet hours",
                  prefs.quiet_hours_enabled === undefined
                    ? "Unavailable"
                    : prefs.quiet_hours_enabled
                      ? `${prefs.quiet_hours_start ?? "Time unavailable"} – ${prefs.quiet_hours_end ?? "Time unavailable"} (${prefs.timezone ?? "Timezone unavailable"})`
                      : "Off",
                ],
                [
                  "Delivery frequency",
                  prefs.digest_mode
                    ? formatReasonCode(prefs.digest_mode)
                    : "Unavailable",
                ],
              ]}
            />
            <label className="flex flex-wrap items-center gap-2 text-text-secondary">
              Minimum alert severity
              <select
                className="rounded border border-border bg-surface-0 px-2 py-1 text-text-primary"
                value={prefs.min_severity}
                disabled={busy}
                onChange={(event) =>
                  void save({ min_severity: event.target.value })
                }
                data-testid="min-severity-select"
              >
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
            </label>
            {prefs.using_defaults ? (
              <p className="text-xs text-text-muted">
                Using default alert preferences.
              </p>
            ) : null}
          </>
        )}
        <div
          className="space-y-2 border-t border-border-subtle pt-3"
          data-testid="settings-notification-context"
        >
          <p className="font-medium text-text-primary">Watcher alert context</p>
          <SettingsReadout
            rows={[
              [
                "Reported markets",
                snapshot
                  ? snapshot.symbols_monitored.join(", ") ||
                    "No markets reported"
                  : "Unavailable",
              ],
              [
                "Reported strategies",
                snapshot
                  ? [
                      ...new Set(
                        snapshot.approved_strategies.map(
                          (strategy) => strategy.name,
                        ),
                      ),
                    ].join(", ") || "No approved strategies reported"
                  : "Unavailable",
              ],
            ]}
          />
          <p className="text-xs text-text-muted">
            This is the reported monitoring context, not a notification filter.
            Per-market and per-strategy notification settings are unavailable.
          </p>
        </div>
        {message ? (
          <p role="status" className="text-xs text-text-secondary">
            {message}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
