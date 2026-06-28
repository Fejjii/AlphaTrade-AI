"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AlertRoutingSummary, PaperAlert, TelegramAlertDeliveryResponse } from "@/lib/api/types";

const CONFIRM_PHRASE = "DELIVER_TELEGRAM_ALERT";

function isTelegramDelivered(alert: PaperAlert): boolean {
  return (
    alert.delivery_channel === "telegram" &&
    alert.delivery_status === "delivered"
  );
}

function deliveryStatusLabel(status: TelegramAlertDeliveryResponse["status"]): string {
  switch (status) {
    case "sent":
      return "Sent to Telegram";
    case "already_delivered":
      return "Already sent to Telegram";
    case "failed_redacted":
      return "Telegram delivery failed";
    case "blocked":
      return "Blocked by safety rules";
    case "skipped_not_configured":
      return "Telegram not configured";
    default:
      return status;
  }
}

export function TelegramManualDeliveryPanel({ routing }: { routing: AlertRoutingSummary }) {
  return (
    <Card data-testid="telegram-manual-delivery-panel">
      <CardHeader>
        <CardTitle className="text-base">Manual Telegram delivery</CardTitle>
        <p className="text-xs text-zinc-500">
          Send selected in-app alerts to Telegram one at a time. No worker automation.
        </p>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2" data-testid="telegram-manual-delivery-badges">
          <StatusBadge label="Paper only" tone="paper" />
          <StatusBadge
            label={routing.worker_enabled ? "Worker enabled" : "Worker disabled"}
            tone={routing.worker_enabled ? "warn" : "paper"}
          />
          <StatusBadge label="Manual delivery only" tone="paper" />
        </div>
        {!routing.telegram_alert_delivery_available ? (
          <p className="mt-3 text-xs text-amber-300/90" data-testid="telegram-delivery-unavailable">
            Manual Telegram delivery unavailable — configure token and chat ID, or resolve safety gates.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function SendAlertToTelegramButton({
  alert,
  routing,
  disabled,
  onComplete,
}: {
  alert: PaperAlert;
  routing: AlertRoutingSummary;
  disabled?: boolean;
  onComplete?: (result: TelegramAlertDeliveryResponse) => void;
}) {
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TelegramAlertDeliveryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const alreadySent = isTelegramDelivered(alert) || result?.status === "already_delivered";
  const confirmMatches = confirmText === CONFIRM_PHRASE;
  const eligible = routing.telegram_alert_delivery_available && !alreadySent;
  const canSend = eligible && confirmMatches && !busy && !disabled;

  async function sendToTelegram() {
    if (!canSend) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.alerts.deliverTelegram(alert.id, { confirm: CONFIRM_PHRASE });
      setResult(response);
      onComplete?.(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Telegram delivery failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!routing.telegram_alert_delivery_available) {
    return null;
  }

  return (
    <div className="space-y-2" data-testid="send-alert-telegram">
      {alreadySent ? (
        <p className="text-xs text-emerald-400/90" data-testid="telegram-already-delivered">
          Already sent to Telegram
          {alert.delivered_at ? ` · ${new Date(alert.delivered_at).toLocaleString()}` : ""}
        </p>
      ) : (
        <>
          <input
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-xs"
            placeholder={`Type ${CONFIRM_PHRASE}`}
            value={confirmText}
            disabled={busy || disabled}
            onChange={(e) => setConfirmText(e.target.value)}
            data-testid="telegram-alert-confirm-input"
          />
          <Button
            variant="outline"
            size="sm"
            disabled={!canSend}
            onClick={() => void sendToTelegram()}
            data-testid="send-alert-telegram-button"
          >
            Send to Telegram
          </Button>
        </>
      )}
      {error ? (
        <p className="text-xs text-red-300" data-testid="telegram-alert-delivery-error">
          {error}
        </p>
      ) : null}
      {result ? (
        <p className="text-xs text-zinc-400" data-testid="telegram-alert-delivery-result">
          {deliveryStatusLabel(result.status)}
          {result.error_message ? (
            <span className="block text-amber-300/90" data-testid="telegram-alert-delivery-result-error">
              {result.error_message}
            </span>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
