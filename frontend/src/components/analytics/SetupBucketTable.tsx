"use client";

import { useMemo } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import type { SourceResult } from "@/components/workflows";
import type {
  JournalStatsResponse,
  SampleConfidence,
  SetupEvidenceResponse,
} from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { SETUP_BUCKET_PAGE_SIZE, isValidUuid } from "./filterValidation";
import { formatMonetary, formatPercent } from "./format";
import { buildSetupBucketRows, type SetupBucketRow } from "./setupBucketTransforms";

const CONFIDENCE_TONE: Record<SampleConfidence, "ok" | "warn" | "critical"> = {
  high: "ok",
  moderate: "ok",
  low: "warn",
  insufficient: "critical",
};

function journalStatsHref(row: SetupBucketRow): string {
  // Drill into the exhaustive numeric table; pass journal UUID identity only when valid.
  if (row.unassigned || !isValidUuid(row.key)) return "/journal/statistics";
  return `/journal/statistics?setup_id=${encodeURIComponent(row.key)}`;
}

function analyticsSetupHref(row: SetupBucketRow, groupBy: string): string {
  if (row.unassigned || !isValidUuid(row.key)) {
    return `/analytics?tab=setups&group_by=${encodeURIComponent(groupBy)}`;
  }
  return `/analytics?tab=setups&setup_id=${encodeURIComponent(row.key)}&group_by=${encodeURIComponent(groupBy)}`;
}

export type SetupBucketTableProps = {
  source: SourceResult<JournalStatsResponse> | null;
  evidence: SourceResult<SetupEvidenceResponse> | null;
  loading?: boolean;
  onRetry?: () => void;
  filtersSummary?: string;
  staleWholeTab?: boolean;
  groupBy: string;
  bucketOffset: number;
  onPageChange: (offset: number) => void;
};

export function SetupBucketTable({
  source,
  evidence,
  loading = false,
  onRetry,
  filtersSummary,
  staleWholeTab = false,
  groupBy,
  bucketOffset,
  onPageChange,
}: SetupBucketTableProps) {
  const derived = useMemo(() => {
    if (!source?.available || !source.data) {
      return {
        rows: [] as SetupBucketRow[],
        sampleSize: 0,
        empty: true,
        truncated: null as { maxRows: number } | null,
        generatedAt: null as string | null,
        totalBuckets: 0,
        limit: SETUP_BUCKET_PAGE_SIZE,
        offset: 0,
      };
    }
    const rows = buildSetupBucketRows(source.data.buckets ?? []);
    const sampleSize = source.data.overall.trade_count;
    return {
      rows,
      sampleSize,
      empty: sampleSize === 0 || rows.length === 0,
      truncated: source.data.truncated ? { maxRows: source.data.max_rows } : null,
      generatedAt: source.data.generated_at,
      totalBuckets: source.data.total_buckets,
      limit: source.data.limit || SETUP_BUCKET_PAGE_SIZE,
      offset: source.data.offset,
    };
  }, [source]);

  const evidenceItems =
    evidence?.available && evidence.data ? evidence.data.items : [];
  const evidenceError = evidence && !evidence.available ? evidence.error : null;
  const pageStart = derived.totalBuckets === 0 ? 0 : derived.offset + 1;
  const pageEnd = Math.min(derived.offset + derived.limit, derived.totalBuckets);
  const canPrev = bucketOffset > 0;
  const canNext = bucketOffset + derived.limit < derived.totalBuckets;
  const showPager = derived.totalBuckets > derived.limit;

  return (
    <ChartFrame
      title="Setup and strategy buckets"
      sourceLabel="GET /journal/statistics · buckets + GET /journal/setup-evidence"
      generatedAt={derived.generatedAt}
      filtersSummary={filtersSummary}
      sampleSize={derived.sampleSize}
      sampleLabel="closed trades"
      loading={loading}
      error={source && !source.available ? source.error ?? "Journal statistics unavailable" : null}
      onRetry={onRetry}
      empty={!loading && source?.available ? derived.empty : false}
      emptyTitle="No setup buckets in this range"
      emptyDescription="Closed journal trades with setup or strategy assignments appear here."
      truncated={derived.truncated}
      staleWholeTab={staleWholeTab}
      data-testid="setup-bucket-table"
    >
      {showPager ? (
        <div
          className="flex flex-wrap items-center gap-2 text-sm text-text-muted"
          data-testid="setup-bucket-pager"
        >
          <span>
            Showing {pageStart}–{pageEnd} of {derived.totalBuckets} buckets
            {derived.truncated ? " · truncated trade coverage" : ""}
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!canPrev}
            onClick={() => onPageChange(Math.max(0, bucketOffset - SETUP_BUCKET_PAGE_SIZE))}
            data-testid="setup-bucket-prev"
          >
            Previous
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!canNext}
            onClick={() => onPageChange(bucketOffset + SETUP_BUCKET_PAGE_SIZE)}
            data-testid="setup-bucket-next"
          >
            Next
          </Button>
        </div>
      ) : null}

      <div className="w-full max-w-full overflow-x-auto">
        <table
          className="min-w-full text-left text-sm"
          data-testid="setup-bucket-data-table"
        >
          <caption className="sr-only">
            Journal setup buckets keyed by stable identity, not display name
          </caption>
          <thead>
            <tr className="border-b border-border-subtle text-text-muted">
              <th className="px-2 py-2 font-medium">Label</th>
              <th className="px-2 py-2 font-medium">Identity key</th>
              <th className="px-2 py-2 font-medium">n</th>
              <th className="px-2 py-2 font-medium">Win rate</th>
              <th className="px-2 py-2 font-medium">Expectancy</th>
              <th className="px-2 py-2 font-medium">Confidence</th>
              <th className="px-2 py-2 font-medium">Links</th>
            </tr>
          </thead>
          <tbody>
            {derived.rows.map((row) => (
              <tr
                key={row.key}
                className="border-b border-border-subtle/60"
                data-testid={`setup-bucket-row-${row.key}`}
              >
                <td className="px-2 py-2 text-text-primary">{row.displayLabel}</td>
                <td className="px-2 py-2 font-data text-caption text-text-muted">{row.key}</td>
                <td className="px-2 py-2 font-data">{row.tradeCount}</td>
                <td className="px-2 py-2 font-data">{formatPercent(row.winRate)}</td>
                <td className="px-2 py-2 font-data">
                  {row.noPnlData ? "No P&L data" : formatMonetary(row.expectancy)}
                </td>
                <td className="px-2 py-2">
                  <StatusBadge
                    label={
                      row.insufficient
                        ? `n=${row.tradeCount} insufficient`
                        : row.confidence
                    }
                    tone={CONFIDENCE_TONE[row.confidence]}
                  />
                </td>
                <td className="px-2 py-2">
                  <div className="flex flex-col gap-1">
                    <Link
                      className="text-accent underline-offset-2 hover:underline"
                      href={journalStatsHref(row)}
                      data-testid={`setup-bucket-stats-link-${row.key}`}
                    >
                      Journal statistics
                    </Link>
                    <Link
                      className="text-accent underline-offset-2 hover:underline"
                      href={analyticsSetupHref(row, groupBy)}
                      data-testid={`setup-bucket-filter-link-${row.key}`}
                    >
                      Filter Setups tab
                    </Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="space-y-2" data-testid="setup-evidence-panel" aria-label="Setup evidence">
        <h3 className="text-sm font-medium text-text-primary">Setup evidence</h3>
        <p className="text-caption text-text-muted">Source: GET /journal/setup-evidence</p>
        {evidenceError ? (
          <p className="text-sm text-amber-500/90" role="status">
            Setup evidence unavailable: {evidenceError}. Bucket table remains from journal
            statistics.
          </p>
        ) : null}
        {!evidenceError && evidenceItems.length === 0 ? (
          <p className="text-sm text-text-muted">No setup-evidence rows for the current filters.</p>
        ) : null}
        {evidenceItems.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {evidenceItems.map((item) => (
              <li
                key={`${item.strategy_id}:${item.strategy_version_id}`}
                className="rounded-control border border-border-subtle px-3 py-2"
                data-testid={`setup-evidence-item-${item.strategy_id}`}
              >
                <p className="font-medium text-text-primary">
                  {item.strategy_name} · v{item.version} · {item.tier}
                </p>
                <p className="font-data text-text-muted">
                  strategy_id {item.strategy_id}
                  {item.measured.oos_expectancy != null
                    ? ` · OOS expectancy ${formatMonetary(item.measured.oos_expectancy)}`
                    : " · OOS expectancy No P&L data"}
                </p>
                <p className="text-caption text-text-muted">{item.note}</p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </ChartFrame>
  );
}
