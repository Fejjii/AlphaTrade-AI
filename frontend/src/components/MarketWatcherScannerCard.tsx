"use client";

import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MarketWatcherSummary } from "@/lib/api/types";

export function MarketWatcherScannerCard({
  summary,
  compact = false,
}: {
  summary: MarketWatcherSummary;
  compact?: boolean;
}) {
  const automationLabel = summary.scanner_enabled ? "automation enabled" : "automation disabled";
  const scanLabel = summary.manual_scan_available ? "manual scan available" : "manual scan blocked";

  return (
    <Card data-testid="market-watcher-scanner-card">
      <CardHeader className={compact ? "pb-2" : undefined}>
        <CardTitle className="text-base">Market Watcher</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-zinc-300">
        <div className="flex flex-wrap gap-2" data-testid="market-watcher-scanner-badges">
          <StatusBadge label={automationLabel} tone={summary.scanner_enabled ? "warn" : "muted"} />
          <StatusBadge
            label={scanLabel}
            tone={summary.manual_scan_available ? "healthy" : "danger"}
          />
          <StatusBadge label={`readiness: ${summary.readiness}`} tone={summary.readiness} />
        </div>
        <p data-testid="market-watcher-last-scan">
          Last scan:{" "}
          {summary.last_scan_at
            ? `${new Date(summary.last_scan_at).toLocaleString()} (${summary.last_scan_status ?? "unknown"})`
            : "never"}
        </p>
        {summary.last_scan_at ? (
          <div className="space-y-1 text-xs text-zinc-400" data-testid="market-watcher-persisted-summary">
            {summary.last_scan_candidate_count > 0 ? (
              <p data-testid="market-watcher-candidate-count">
                Candidates: {summary.last_scan_candidate_count}
              </p>
            ) : null}
            {summary.last_scan_alerts_deduped > 0 ? (
              <p data-testid="market-watcher-alerts-deduped">
                Deduped on last scan: {summary.last_scan_alerts_deduped}
              </p>
            ) : null}
            {summary.last_scan_dry_run != null ? (
              <p data-testid="market-watcher-last-scan-mode">
                Mode: {summary.last_scan_dry_run ? "dry-run" : "in-app alerts"}
              </p>
            ) : null}
          </div>
        ) : null}
        {summary.last_scan_alerts_created > 0 ? (
          <p data-testid="market-watcher-alerts-created">
            In-app alerts created on last scan: {summary.last_scan_alerts_created}
          </p>
        ) : null}
        {summary.warnings.length ? (
          <ul className="text-xs text-amber-400" data-testid="market-watcher-warnings">
            {summary.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : null}
        {summary.detectors_enabled?.length ? (
          <p className="text-xs text-zinc-500" data-testid="market-watcher-detectors">
            Setup detectors: {summary.detectors_enabled.join(", ")}
            {summary.last_scan_conditions_found?.length
              ? ` · last scan: ${summary.last_scan_conditions_found.join(", ")}`
              : ""}
          </p>
        ) : null}
        <Link href="/watcher" className="text-xs text-sky-400 underline">
          Open watcher scanner
        </Link>
      </CardContent>
    </Card>
  );
}
