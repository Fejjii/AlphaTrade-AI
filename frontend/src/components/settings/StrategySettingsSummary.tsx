"use client";

import Link from "next/link";
import { useCallback } from "react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { WatcherMonitoringSnapshot } from "@/lib/api/types";
import { formatReasonCode, watcherStatusTone } from "@/lib/watcher-monitoring";
import { SettingsUnavailable } from "./SettingsReadout";

export function StrategySettingsSummary({
  snapshot,
  loading,
  onRetry,
}: {
  snapshot: WatcherMonitoringSnapshot | null;
  loading: boolean;
  onRetry: () => void;
}) {
  const versionLoader = useCallback(async () => {
    const ids = [
      ...new Set(
        snapshot?.approved_strategies.map((row) => row.strategy_id) ?? [],
      ),
    ];
    const results = await Promise.allSettled(
      ids.map((id) => api.strategies.listVersions(id)),
    );
    return new Map(
      results.flatMap((result) =>
        result.status === "fulfilled"
          ? result.value.items.map(
              (version) => [version.id, version.version] as const,
            )
          : [],
      ),
    );
  }, [snapshot]);
  const versions = useAsyncData(versionLoader, [versionLoader]);

  return (
    <Card data-testid="settings-strategies-summary">
      <CardHeader>
        <p className="text-sm text-text-muted">
          Strategy versions approved for Watcher monitoring and active paper
          use.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {loading || !snapshot ? (
          <SettingsUnavailable
            label="Strategy monitoring"
            loading={loading}
            onRetry={onRetry}
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span>Paper monitoring</span>
              <StatusBadge
                label={formatReasonCode(
                  snapshot.paper_monitoring_status.toLowerCase(),
                )}
                tone={watcherStatusTone(snapshot.paper_monitoring_status)}
              />
            </div>
            {snapshot.approved_strategies.length ? (
              <ul className="space-y-3">
                {snapshot.approved_strategies.map((strategy) => {
                  const version = versions.data?.get(
                    strategy.strategy_version_id,
                  );
                  return (
                    <li
                      key={strategy.strategy_version_id}
                      className="min-w-0 space-y-1 border-b border-border-subtle pb-3"
                    >
                      <Link
                        href={`/strategies/${strategy.strategy_id}`}
                        className="text-text-primary underline"
                      >
                        {strategy.name}
                      </Link>
                      <p className="text-text-secondary">
                        {version != null
                          ? `Version ${version}`
                          : versions.loading
                            ? "Loading version…"
                            : "Version number unavailable"}
                        {" · "}
                        {strategy.lifecycle_state === "active"
                          ? "Active paper version"
                          : strategy.lifecycle_state === "approved"
                            ? "Approved for monitoring"
                            : formatReasonCode(strategy.lifecycle_state)}
                      </p>
                      <details className="text-xs text-text-muted">
                        <summary className="cursor-pointer">
                          Version reference
                        </summary>
                        <p className="mt-1 break-all">
                          {strategy.strategy_version_id}
                        </p>
                      </details>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-text-muted">
                No approved or active paper strategy versions reported.
              </p>
            )}
            <p className="text-text-secondary">
              Setups detected in the last scan:{" "}
              {snapshot.scanner_candidates.count}
            </p>
            <p className="text-xs text-text-muted">
              Strategy activation controls are unavailable in this workspace.
              Approval alone does not confirm that monitoring is running.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
