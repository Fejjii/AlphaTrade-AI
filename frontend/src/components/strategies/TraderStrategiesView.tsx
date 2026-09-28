"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import {
  isHttpEvidenceRef,
  patternsFromCard,
  performanceForStrategy,
  rulesFromCard,
} from "@/components/strategies/trader-strategies";
import type { SourceResult } from "@/components/workflows/sourceResult";
import { api } from "@/lib/api";
import { formatMonetary, formatPercent, UNAVAILABLE } from "@/lib/format";
import { strategyStatusFor } from "@/lib/strategy-status";
import type {
  JournalEntry,
  JournalStatsResponse,
  PaginatedUserStrategies,
  UserStrategyVersion,
} from "@/lib/api/types";

export type TraderStrategiesData = {
  strategies: SourceResult<PaginatedUserStrategies>;
  stats: SourceResult<JournalStatsResponse>;
  journal: SourceResult<{ items: JournalEntry[] }>;
};

function BulletList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-text-muted">{empty}</p>;
  return (
    <ul className="list-disc space-y-1 pl-4 text-sm text-text-secondary">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function TraderStrategiesView({ data }: { data: TraderStrategiesData }) {
  const strategies = data.strategies.available ? (data.strategies.data?.items ?? []) : null;
  const buckets = data.stats.available ? (data.stats.data?.buckets ?? []) : null;
  const entries = data.journal.available ? (data.journal.data?.items ?? []) : null;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [versions, setVersions] = useState<UserStrategyVersion[] | null>(null);
  const [versionsError, setVersionsError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId) {
      setVersions(null);
      setVersionsError(null);
      return;
    }
    let cancelled = false;
    setVersions(null);
    setVersionsError(null);
    void api.strategies
      .listVersions(selectedId)
      .then((page) => {
        if (!cancelled) setVersions(page.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setVersionsError(error instanceof Error ? error.message : "Versions unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const selected = strategies?.find((item) => item.id === selectedId) ?? null;

  return (
    <div className="space-y-6" data-testid="trader-strategies">
      <PageHeader
        title="Strategies"
        description="Rules, versions, evidence, and results for each strategy."
        actions={
          <Link
            href="/strategy-lab/new"
            className="inline-flex h-10 items-center rounded-control bg-accent px-4 text-sm text-accent-foreground"
          >
            New strategy
          </Link>
        }
      />

      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/strategy-lab" className="text-accent hover:underline">
          Strategy Lab
        </Link>
        <Link href="/knowledge" className="text-accent hover:underline">
          Knowledge
        </Link>
      </div>

      {strategies == null ? (
        <p className="text-sm text-text-muted">Strategies unavailable</p>
      ) : strategies.length === 0 ? (
        <p className="text-sm text-text-muted">No strategies yet.</p>
      ) : (
        <ul className="grid gap-3">
          {strategies.map((strategy) => {
            const status = strategyStatusFor(strategy);
            const active = strategy.id === selectedId;
            return (
              <li key={strategy.id}>
                <button
                  type="button"
                  data-testid="strategy-row"
                  aria-pressed={active}
                  className="w-full rounded-card border border-border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
                  onClick={() => setSelectedId(active ? null : strategy.id)}
                >
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium text-text-primary">{strategy.name}</span>
                    <span className="flex items-center gap-2">
                      <Badge variant={status.variant}>{status.label}</Badge>
                      <span className="text-caption text-text-muted">v{strategy.current_version}</span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {selected ? (
        <Card data-testid="strategy-detail">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{selected.name}</CardTitle>
            <Link href={`/strategy-lab/${selected.id}`} className="text-sm text-accent hover:underline">
              Open in Strategy Lab
            </Link>
          </CardHeader>
          <CardContent className="grid gap-6 lg:grid-cols-2">
            <div>
              <h2 className="mb-2 text-sm font-medium text-text-primary">Patterns</h2>
              <BulletList
                items={patternsFromCard(selected.latest_card)}
                empty="No patterns on the latest version."
              />
            </div>
            <div>
              <h2 className="mb-2 text-sm font-medium text-text-primary">Rules</h2>
              <BulletList
                items={rulesFromCard(selected.latest_card)}
                empty="Rules not captured on the latest version."
              />
            </div>
            <div>
              <h2 className="mb-2 text-sm font-medium text-text-primary">Performance</h2>
              {buckets == null ? (
                <p className="text-sm text-text-muted">Performance unavailable</p>
              ) : (
                <StrategyPerformance strategyId={selected.id} name={selected.name} buckets={buckets} />
              )}
            </div>
            <div>
              <h2 className="mb-2 text-sm font-medium text-text-primary">Versions</h2>
              {versionsError ? (
                <p className="text-sm text-text-muted">Versions unavailable</p>
              ) : versions == null ? (
                <p className="text-sm text-text-muted">Loading versions…</p>
              ) : versions.length === 0 ? (
                <p className="text-sm text-text-muted">No versions returned.</p>
              ) : (
                <ul className="space-y-1 text-sm text-text-secondary">
                  {versions.map((version) => (
                    <li key={version.id}>
                      v{version.version} · {version.validation_status}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="lg:col-span-2">
              <h2 className="mb-2 text-sm font-medium text-text-primary">Evidence</h2>
              <EvidenceList
                entries={entries}
                strategyId={selected.id}
              />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {buckets && buckets.length > 0 ? (
        <Card data-testid="strategy-performance-list">
          <CardHeader>
            <CardTitle>Results by strategy</CardTitle>
          </CardHeader>
          <CardContent>
            <ul>
              {buckets.map((bucket) => (
                <li
                  key={`${bucket.key}-${bucket.label}`}
                  className="flex items-baseline justify-between gap-3 border-b border-border-subtle py-2 text-sm last:border-b-0"
                >
                  <span className="text-text-primary">{bucket.label}</span>
                  <span className="font-data text-text-secondary">
                    {formatMonetary(bucket.metrics.net_pnl_total)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function StrategyPerformance({
  strategyId,
  name,
  buckets,
}: {
  strategyId: string;
  name: string;
  buckets: JournalStatsResponse["buckets"];
}) {
  const match = performanceForStrategy({ id: strategyId, name }, buckets);
  if (!match) return <p className="text-sm text-text-muted">No journal performance for this strategy.</p>;
  const win =
    match.metrics.trade_count > 0 && match.metrics.win_rate != null
      ? formatPercent(match.metrics.win_rate)
      : UNAVAILABLE;
  return (
    <p className="text-sm text-text-secondary">
      {formatMonetary(match.metrics.net_pnl_total)} · win rate {win}
    </p>
  );
}

function EvidenceList({
  entries,
  strategyId,
}: {
  entries: JournalEntry[] | null;
  strategyId: string;
}) {
  if (entries == null) return <p className="text-sm text-text-muted">Evidence unavailable</p>;
  const refs = entries
    .filter((entry) => entry.strategy_id === strategyId)
    .flatMap((entry) => entry.screenshot_refs.map((ref) => ({ entryId: entry.id, ref })));
  if (refs.length === 0) {
    return <p className="text-sm text-text-muted">No screenshots linked to this strategy.</p>;
  }
  return (
    <ul className="space-y-1 text-sm">
      {refs.map((item) => (
        <li key={`${item.entryId}-${item.ref}`}>
          {isHttpEvidenceRef(item.ref) ? (
            <a href={item.ref} className="text-accent hover:underline" rel="noreferrer">
              {item.ref}
            </a>
          ) : (
            <span className="text-text-secondary">{item.ref}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
