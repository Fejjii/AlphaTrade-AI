"use client";

import { useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { AlertDeliveryPreviewResponse, AlertRoutingSummary } from "@/lib/api/types";

export function AutomaticTelegramDeliveryReadinessPanel({
  routing,
}: {
  routing: AlertRoutingSummary;
}) {
  return (
    <Card data-testid="automatic-telegram-readiness-panel">
      <CardHeader>
        <CardTitle className="text-base">Automatic Telegram delivery readiness</CardTitle>
        <p className="text-xs text-zinc-500">
          Preview-only in this release — no automatic sends from this panel.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2" data-testid="automatic-delivery-badges">
          <StatusBadge label="Paper only" tone="paper" />
          <StatusBadge
            label={routing.worker_enabled ? "Worker enabled" : "Worker disabled"}
            tone={routing.worker_enabled ? "warn" : "paper"}
          />
          {routing.dry_run_supported ? (
            <StatusBadge label="Dry-run supported" tone="paper" />
          ) : null}
          <StatusBadge
            label={
              routing.telegram_configured && routing.telegram_chat_configured
                ? "Telegram configured"
                : "Telegram not configured"
            }
            tone={
              routing.telegram_configured && routing.telegram_chat_configured ? "healthy" : "warn"
            }
          />
          <StatusBadge
            label={
              routing.automatic_telegram_delivery_ready ? "Auto ready" : "Auto not ready"
            }
            tone={routing.automatic_telegram_delivery_ready ? "healthy" : "warn"}
          />
        </div>

        <dl className="grid gap-2 text-xs text-zinc-400 sm:grid-cols-2">
          <div>
            <dt className="text-zinc-500">Eligible pending</dt>
            <dd data-testid="eligible-pending-count">{routing.eligible_pending_telegram_count}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Already delivered</dt>
            <dd data-testid="already-delivered-count">
              {routing.already_delivered_telegram_count}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Next preview batch</dt>
            <dd>{routing.next_delivery_preview_count}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Preview limit</dt>
            <dd>{routing.delivery_limits?.default_preview_limit ?? 5}</dd>
          </div>
        </dl>

        {routing.automatic_delivery_blockers.length ? (
          <ul
            className="list-inside list-disc text-xs text-amber-300/90"
            data-testid="automatic-delivery-blockers"
          >
            {routing.automatic_delivery_blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function PreviewTelegramDeliveryButton({
  disabled,
  limit = 5,
}: {
  disabled?: boolean;
  limit?: number;
}) {
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<AlertDeliveryPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runPreview() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.alerts.previewDelivery({
        channel: "telegram",
        limit,
        severity_min: "info",
      });
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2" data-testid="telegram-delivery-preview">
      <Button
        variant="outline"
        size="sm"
        disabled={disabled || busy}
        onClick={() => void runPreview()}
        data-testid="preview-telegram-delivery-button"
      >
        Preview eligible Telegram alerts
      </Button>
      {error ? (
        <p className="text-xs text-red-300" data-testid="preview-error">
          {error}
        </p>
      ) : null}
      {preview ? (
        <div className="rounded border border-zinc-800 p-3 text-xs" data-testid="preview-results">
          <p data-testid="preview-eligible-count">
            Eligible: {preview.eligible_count} · Skipped: {preview.skipped_count} · Already
            delivered: {preview.already_delivered_count}
          </p>
          <ul className="mt-2 space-y-1">
            {preview.items.map((item) => (
              <li key={item.alert_id} data-testid="preview-item">
                <span className="font-mono text-zinc-500">{item.status}</span> —{" "}
                {item.message_preview}
                {item.reason ? (
                  <span className="block text-zinc-500">{item.reason}</span>
                ) : null}
              </li>
            ))}
          </ul>
          {preview.warnings.length ? (
            <ul className="mt-2 list-inside list-disc text-amber-300/90">
              {preview.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
