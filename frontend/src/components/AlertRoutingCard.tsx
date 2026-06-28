"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AlertRoutingSummary } from "@/lib/api/types";

function readinessTone(readiness: AlertRoutingSummary["readiness"]) {
  if (readiness === "ready") return "healthy";
  if (readiness === "degraded") return "warn";
  return "blocked";
}

function quietHoursLabel(quietHours: AlertRoutingSummary["quiet_hours"]): string {
  if (!quietHours.enabled) return "Off";
  return `${quietHours.start ?? "—"}–${quietHours.end ?? "—"} (${quietHours.timezone})`;
}

function bridgeDecisionLabel(decision: string | null | undefined): string {
  if (!decision) return "No bridge activity yet";
  return decision.replace(/_/g, " ");
}

export function AlertRoutingCard({
  routing,
  compact = false,
}: {
  routing: AlertRoutingSummary;
  compact?: boolean;
}) {
  return (
    <Card data-testid="alert-routing-card">
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="text-base">Alerts &amp; market watcher</CardTitle>
          <p className="mt-1 text-xs text-zinc-500">
            Alert routing and bridge readiness — read-only, no notifications sent from this view.
          </p>
        </div>
        <StatusBadge label={routing.readiness} tone={readinessTone(routing.readiness)} />
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="flex flex-wrap gap-2" data-testid="alert-routing-safety-badges">
          <StatusBadge label="Paper only" tone="paper" />
          <StatusBadge
            label={
              routing.external_delivery_enabled
                ? "External delivery enabled"
                : "External delivery disabled"
            }
            tone={routing.external_delivery_enabled ? "warn" : "paper"}
          />
          <StatusBadge
            label={routing.telegram_enabled ? "Telegram enabled" : "Telegram disabled"}
            tone={routing.telegram_enabled ? "warn" : "paper"}
          />
          <StatusBadge
            label={routing.worker_enabled ? "Worker enabled" : "Worker disabled"}
            tone={routing.worker_enabled ? "warn" : "paper"}
          />
        </div>

        {routing.readiness === "blocked" ? (
          <p
            className="rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-200"
            data-testid="alert-routing-blocked-warning"
          >
            Alert routing is blocked. Resolve warnings before enabling external delivery.
          </p>
        ) : null}

        {routing.readiness === "degraded" ? (
          <p
            className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-200"
            data-testid="alert-routing-degraded-warning"
          >
            Alert routing is degraded — review bridge and delivery warnings below.
          </p>
        ) : null}

        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-zinc-500">In-app alerts</dt>
            <dd className="text-zinc-200">{routing.alerts_enabled ? "Active" : "Inactive"}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Webhook</dt>
            <dd className="text-zinc-200">
              {routing.webhook_enabled ? "Enabled in config" : "Disabled"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Quiet hours</dt>
            <dd className="text-zinc-200">{quietHoursLabel(routing.quiet_hours)}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Severity filters</dt>
            <dd className="text-zinc-200">{routing.severity_filters.join(" · ") || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Pending alerts</dt>
            <dd className="text-zinc-200">{routing.pending_alerts_count}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Failed deliveries</dt>
            <dd className="text-zinc-200">{routing.failed_alerts_count}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Market watcher</dt>
            <dd className="text-zinc-200">
              {routing.market_watcher_configured
                ? routing.market_watcher_running
                  ? "Running"
                  : "Configured, idle"
                : "Not configured"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Bridge</dt>
            <dd className="text-zinc-200">
              {routing.bridge_enabled
                ? routing.bridge_running
                  ? "Running"
                  : "Configured, not ticking"
                : "Disabled"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Last bridge decision</dt>
            <dd className="text-zinc-200">{bridgeDecisionLabel(routing.bridge_last_decision)}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Last bridge tick</dt>
            <dd className="text-zinc-200">
              {routing.bridge_last_tick_at
                ? new Date(routing.bridge_last_tick_at).toLocaleString()
                : "—"}
            </dd>
          </div>
          {routing.bridge_last_error ? (
            <div className="sm:col-span-2">
              <dt className="text-xs text-zinc-500">Last bridge error</dt>
              <dd className="text-zinc-200">{routing.bridge_last_error}</dd>
            </div>
          ) : null}
        </dl>

        {routing.warnings.length ? (
          <div data-testid="alert-routing-warnings">
            <p className="mb-1 text-xs font-medium text-amber-400">Warnings</p>
            <ul className="space-y-1 text-xs text-amber-200/90">
              {routing.warnings.map((warning) => (
                <li key={warning}>• {warning}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {compact ? (
          <Link href="/alerts" className="inline-block text-xs text-zinc-400 underline">
            Open alerts &amp; routing details
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}
