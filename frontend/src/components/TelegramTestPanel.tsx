"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AlertRoutingSummary, TelegramTestAlertResponse } from "@/lib/api/types";

const CONFIRM_PHRASE = "SEND_TEST_TELEGRAM";

function statusLabel(status: TelegramTestAlertResponse["status"]): string {
  switch (status) {
    case "sent":
      return "Test alert sent";
    case "skipped_not_configured":
      return "Skipped — Telegram not fully configured";
    case "blocked":
      return "Blocked by safety rules";
    case "failed_redacted":
      return "Delivery failed";
    default:
      return status;
  }
}

export function TelegramTestPanel({ routing }: { routing: AlertRoutingSummary }) {
  const [confirmText, setConfirmText] = useState("");
  const [operatorMessage, setOperatorMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TelegramTestAlertResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const confirmMatches = confirmText === CONFIRM_PHRASE;
  const canSend = routing.manual_test_available && confirmMatches && !busy;

  async function sendTest() {
    if (!confirmMatches) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const response = await api.alerts.testTelegram({
        confirm: CONFIRM_PHRASE,
        message: operatorMessage.trim() || undefined,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Telegram test failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card data-testid="telegram-test-panel">
      <CardHeader>
        <CardTitle className="text-base">Telegram test alert</CardTitle>
        <p className="text-xs text-zinc-500">
          Owner-only manual test — sends one safe message when configured. No trades executed.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="flex flex-wrap gap-2" data-testid="telegram-test-badges">
          <StatusBadge label="Paper only" tone="paper" />
          <StatusBadge
            label={routing.worker_enabled ? "Worker enabled" : "Worker disabled"}
            tone={routing.worker_enabled ? "warn" : "paper"}
          />
          <span data-testid="telegram-configured-badge">
            <StatusBadge
              label={
                routing.telegram_configured ? "Telegram configured" : "Telegram missing token"
              }
              tone={routing.telegram_configured ? "healthy" : "blocked"}
            />
          </span>
          <span data-testid="telegram-chat-badge">
            <StatusBadge
              label={
                routing.telegram_chat_configured ? "Chat configured" : "Chat missing"
              }
              tone={routing.telegram_chat_configured ? "healthy" : "blocked"}
            />
          </span>
        </div>

        {!routing.manual_test_available ? (
          <p
            className="rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-200"
            data-testid="telegram-test-unavailable"
          >
            Manual Telegram test is unavailable — paper-only safety gates are not satisfied.
          </p>
        ) : null}

        {routing.last_test_alert_at ? (
          <p className="text-xs text-zinc-500" data-testid="telegram-last-test">
            Last test: {routing.last_test_alert_status ?? "unknown"} at{" "}
            {new Date(routing.last_test_alert_at).toLocaleString()}
          </p>
        ) : null}

        <div className="space-y-2">
          <label className="block text-xs text-zinc-400" htmlFor="telegram-operator-message">
            Optional short note (operator-safe, max 200 chars)
          </label>
          <input
            id="telegram-operator-message"
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
            value={operatorMessage}
            maxLength={200}
            disabled={busy || !routing.manual_test_available}
            onChange={(e) => setOperatorMessage(e.target.value)}
            data-testid="telegram-operator-message"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-xs text-zinc-400" htmlFor="telegram-confirm-input">
            Type <span className="font-mono text-zinc-300">{CONFIRM_PHRASE}</span> to confirm
          </label>
          <input
            id="telegram-confirm-input"
            className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 font-mono text-sm"
            value={confirmText}
            disabled={busy || !routing.manual_test_available}
            onChange={(e) => setConfirmText(e.target.value)}
            data-testid="telegram-confirm-input"
          />
        </div>

        <Button
          variant="secondary"
          size="sm"
          disabled={!canSend}
          onClick={() => void sendTest()}
          data-testid="telegram-test-send"
        >
          Send Telegram test
        </Button>

        {error ? (
          <p className="text-xs text-red-300" data-testid="telegram-test-error">
            {error}
          </p>
        ) : null}

        {result ? (
          <div
            className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-xs"
            data-testid="telegram-test-result"
          >
            <p className="font-medium text-zinc-200">{statusLabel(result.status)}</p>
            <p className="text-zinc-500">Status: {result.status}</p>
            {result.sent_at ? (
              <p className="text-zinc-500">
                Sent at {new Date(result.sent_at).toLocaleString()}
              </p>
            ) : null}
            {result.error_message ? (
              <p className="text-amber-300/90" data-testid="telegram-test-result-error">
                {result.error_message}
              </p>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
