"use client";

import type { ReactNode } from "react";

import { FreshnessPill } from "@/components/ui/freshness-pill";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  EmptyState,
  ErrorState,
  LimitationsState,
  LoadingState,
  StaleState,
} from "@/components/states";
import { freshnessFromTimestamp } from "@/components/workflows/freshness";
import { cn } from "@/lib/utils";

export type ChartFrameProps = {
  title: string;
  sourceLabel: string;
  generatedAt?: string | null;
  filtersSummary?: string;
  sampleSize?: number | null;
  sampleLabel?: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  empty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  limitations?: string[];
  truncated?: { maxRows: number } | null;
  insufficientSample?: { n: number; min?: number } | null;
  derivedNote?: string;
  staleWholeTab?: boolean;
  className?: string;
  children?: ReactNode;
  "data-testid"?: string;
};

export function ChartFrame({
  title,
  sourceLabel,
  generatedAt,
  filtersSummary,
  sampleSize,
  sampleLabel = "sample",
  loading = false,
  error = null,
  onRetry,
  empty = false,
  emptyTitle = "No data in this range",
  emptyDescription,
  emptyAction,
  limitations = [],
  truncated = null,
  insufficientSample = null,
  derivedNote,
  staleWholeTab = false,
  className,
  children,
  "data-testid": testId = "chart-frame",
}: ChartFrameProps) {
  const freshness = freshnessFromTimestamp(generatedAt ?? null);

  return (
    <Card className={cn(className)} data-testid={testId}>
      <CardHeader className="space-y-2 pb-3">
        <CardTitle className="text-base font-medium">{title}</CardTitle>
        <div className="flex flex-wrap items-center gap-2 text-caption text-text-muted">
          <span data-testid={`${testId}-source`}>{sourceLabel}</span>
          {generatedAt ? (
            <span data-testid={`${testId}-generated-at`}>as of {generatedAt}</span>
          ) : null}
          {filtersSummary ? <span>{filtersSummary}</span> : null}
          {sampleSize != null ? (
            <span data-testid={`${testId}-sample`}>
              n={sampleSize} {sampleLabel}
            </span>
          ) : null}
          {freshness ? (
            <FreshnessPill state={freshness.state} ageLabel={freshness.ageLabel} />
          ) : null}
          {insufficientSample ? (
            <span
              className="rounded bg-surface-2 px-2 py-0.5 text-caption text-text-muted"
              data-testid={`${testId}-insufficient`}
            >
              n={insufficientSample.n}
              {insufficientSample.min != null ? ` — insufficient (< ${insufficientSample.min})` : " — insufficient"}
            </span>
          ) : null}
        </div>
        {derivedNote ? (
          <p className="text-caption text-text-muted" data-testid={`${testId}-derived-note`}>
            {derivedNote}
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {staleWholeTab ? (
          <StaleState message="Analytics sources may be delayed or stale for this view." />
        ) : null}
        {truncated ? (
          <LimitationsState
            title="Truncated coverage"
            message={`Statistics cover the oldest ${truncated.maxRows} closed trades in range — narrow the date range for complete coverage.`}
          />
        ) : null}
        {limitations.length ? (
          <LimitationsState items={limitations} message="Some metrics carry explicit limitations." />
        ) : null}
        {loading ? <LoadingState label={`Loading ${title.toLowerCase()}…`} /> : null}
        {!loading && error ? (
          <div data-testid={`${testId}-error`}>
            <ErrorState message={error} onRetry={onRetry} />
          </div>
        ) : null}
        {!loading && !error && empty ? (
          <div className="space-y-3" data-testid={`${testId}-empty`}>
            <EmptyState title={emptyTitle} description={emptyDescription} />
            {emptyAction ? (
              <div className="flex justify-center">{emptyAction}</div>
            ) : null}
          </div>
        ) : null}
        {!loading && !error && !empty ? children : null}
      </CardContent>
    </Card>
  );
}
