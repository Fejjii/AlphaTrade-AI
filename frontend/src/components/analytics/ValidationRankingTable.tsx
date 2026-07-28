"use client";

import { useMemo } from "react";
import Link from "next/link";

import type { SourceResult } from "@/components/workflows";
import type {
  SetupRankingResponse,
  StrategyQualitySummaryResponse,
} from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { NO_SERVER_FRESHNESS_TIMESTAMP_NOTE } from "./sourceFreshness";

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

export type ValidationRankingTableProps = {
  rankingSource: SourceResult<SetupRankingResponse> | null;
  strategyQualitySource: SourceResult<StrategyQualitySummaryResponse> | null;
  rankingLoading?: boolean;
  strategyQualityLoading?: boolean;
  onRetryRanking?: () => void;
  onRetryStrategyQuality?: () => void;
  rankingFiltersSummary?: string;
  strategyQualityFiltersSummary?: string;
};

export function ValidationRankingTable({
  rankingSource,
  strategyQualitySource,
  rankingLoading = false,
  strategyQualityLoading = false,
  onRetryRanking,
  onRetryStrategyQuality,
  rankingFiltersSummary,
  strategyQualityFiltersSummary,
}: ValidationRankingTableProps) {
  const ranking = useMemo(() => {
    if (!rankingSource?.available || !rankingSource.data) {
      return {
        rows: [] as SetupRankingResponse["ranked"],
        note: null as string | null,
        minSample: null as number | null,
        empty: true,
        dimension: null as string | null,
      };
    }
    return {
      rows: rankingSource.data.ranked ?? [],
      note: rankingSource.data.note || null,
      minSample: rankingSource.data.min_sample,
      empty: (rankingSource.data.ranked ?? []).length === 0,
      dimension: rankingSource.data.dimension,
    };
  }, [rankingSource]);

  const strategyContext = useMemo(() => {
    if (!strategyQualitySource?.available || !strategyQualitySource.data) {
      return null;
    }
    const data = strategyQualitySource.data;
    return {
      note: data.note || null,
      totalDetectors: data.total_detectors,
      detectorsWithData: data.detectors_with_data,
      totalResults: data.total_results,
      byVerdict: data.by_verdict ?? [],
      byTrustTier: data.by_trust_tier ?? [],
      warnings: data.warnings ?? [],
      minSample: data.min_sample,
    };
  }, [strategyQualitySource]);

  return (
    <div className="space-y-6" data-testid="validation-ranking-section">
      <ChartFrame
        title="Validation setup ranking"
        sourceLabel="GET /learning-analytics/setup-ranking"
        filtersSummary={rankingFiltersSummary}
        sampleSize={rankingSource?.available ? ranking.rows.length : null}
        sampleLabel="ranked setups"
        loading={rankingLoading}
        error={
          rankingSource && !rankingSource.available
            ? rankingSource.error ?? "Setup ranking unavailable"
            : null
        }
        onRetry={onRetryRanking}
        empty={!rankingLoading && rankingSource?.available ? ranking.empty : false}
        emptyTitle="No ranking yet"
        emptyDescription="Ranking appears once enough sessions meet the minimum sample size."
        emptyAction={
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link
              href="/paper-validation/run-sessions"
              className="text-accent underline-offset-2 hover:underline"
              data-testid="validation-ranking-empty-sessions-link"
            >
              Open run sessions
            </Link>
            <Link
              href="/strategy-quality"
              className="text-accent underline-offset-2 hover:underline"
              data-testid="validation-ranking-empty-strategy-quality-link"
            >
              Strategy quality
            </Link>
          </div>
        }
        derivedNote={NO_SERVER_FRESHNESS_TIMESTAMP_NOTE}
        data-testid="validation-ranking-table"
      >
        {ranking.note ? (
          <p className="text-caption text-text-muted" data-testid="validation-ranking-note">
            {ranking.note}
          </p>
        ) : null}
        <p className="text-caption text-text-muted" data-testid="validation-ranking-links">
          Detail pages:{" "}
          <Link
            href="/paper-validation/run-sessions"
            className="text-accent underline-offset-2 hover:underline"
          >
            /paper-validation/run-sessions
          </Link>
          {" · "}
          <Link
            href="/strategy-quality"
            className="text-accent underline-offset-2 hover:underline"
          >
            /strategy-quality
          </Link>
        </p>

        <div className="w-full max-w-full overflow-x-auto">
          <table
            className="w-full min-w-[480px] text-left text-sm"
            data-testid="validation-ranking-data-table"
          >
            <caption className="sr-only">
              Learning-analytics setup ranking by detector condition identity
            </caption>
            <thead>
              <tr className="border-b border-border-subtle text-caption text-text-muted">
                <th className="px-2 py-2 font-medium">Rank</th>
                <th className="px-2 py-2 font-medium">Setup / condition</th>
                <th className="px-2 py-2 font-medium">Quality score</th>
                <th className="px-2 py-2 font-medium">Sample size</th>
                <th className="px-2 py-2 font-medium">Reliability</th>
              </tr>
            </thead>
            <tbody>
              {ranking.rows.map((row) => {
                const insufficient =
                  ranking.minSample != null && row.sample_size < ranking.minSample;
                return (
                  <tr
                    key={`${row.rank}-${row.setup_key}`}
                    className={
                      insufficient
                        ? "border-b border-border-subtle/60 text-text-muted"
                        : "border-b border-border-subtle/60 text-text-secondary"
                    }
                    data-testid={`validation-ranking-row-${row.setup_key}`}
                  >
                    <td className="px-2 py-2 font-data">
                      {row.rank == null ? "—" : row.rank}
                    </td>
                    <td className="px-2 py-2">
                      <Link
                        href="/strategy-quality"
                        className="text-accent underline-offset-2 hover:underline"
                      >
                        {row.setup_key || "—"}
                      </Link>
                    </td>
                    <td className="px-2 py-2 font-data">
                      {formatScore(row.quality_score)}
                    </td>
                    <td className="px-2 py-2 font-data" data-testid={`validation-ranking-n-${row.setup_key}`}>
                      {row.sample_size == null ? "—" : row.sample_size}
                    </td>
                    <td className="px-2 py-2">
                      {insufficient ? "insufficient data" : "ranked"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </ChartFrame>

      <ChartFrame
        title="Strategy quality context"
        sourceLabel="GET /strategy-quality/summary"
        filtersSummary={strategyQualityFiltersSummary}
        sampleSize={
          strategyContext ? strategyContext.detectorsWithData : null
        }
        sampleLabel="detectors with data"
        loading={strategyQualityLoading}
        error={
          strategyQualitySource && !strategyQualitySource.available
            ? strategyQualitySource.error ?? "Strategy quality summary unavailable"
            : null
        }
        onRetry={onRetryStrategyQuality}
        empty={
          !strategyQualityLoading &&
          strategyQualitySource?.available &&
          strategyContext != null &&
          strategyContext.totalDetectors === 0 &&
          strategyContext.totalResults === 0
        }
        emptyTitle="No strategy-quality summary yet"
        emptyDescription="Detector calibration detail lives on /strategy-quality — this card is compact context only."
        emptyAction={
          <Link
            href="/strategy-quality"
            className="text-accent underline-offset-2 hover:underline"
            data-testid="validation-sq-empty-link"
          >
            Open strategy quality
          </Link>
        }
        derivedNote={NO_SERVER_FRESHNESS_TIMESTAMP_NOTE}
        data-testid="validation-strategy-quality-context"
      >
        {strategyContext ? (
          <div className="space-y-3 text-sm text-text-secondary">
            {strategyContext.note ? (
              <p className="text-caption text-text-muted" data-testid="validation-sq-note">
                {strategyContext.note}
              </p>
            ) : null}
            <p data-testid="validation-sq-counts">
              {strategyContext.detectorsWithData == null
                ? "—"
                : strategyContext.detectorsWithData}{" "}
              of{" "}
              {strategyContext.totalDetectors == null
                ? "—"
                : strategyContext.totalDetectors}{" "}
              detectors have validated results (
              {strategyContext.totalResults == null
                ? "—"
                : strategyContext.totalResults}{" "}
              total). Compact context only — detector-calibration charts stay on{" "}
              <Link
                href="/strategy-quality"
                className="text-accent underline-offset-2 hover:underline"
              >
                /strategy-quality
              </Link>
              .
            </p>
            {strategyContext.byVerdict.length ? (
              <ul
                className="flex flex-wrap gap-3 text-caption"
                data-testid="validation-sq-verdicts"
              >
                {strategyContext.byVerdict.map((row) => (
                  <li key={row.verdict}>
                    {row.verdict}: {row.count == null ? "—" : row.count}
                  </li>
                ))}
              </ul>
            ) : null}
            {strategyContext.byTrustTier.length ? (
              <ul
                className="flex flex-wrap gap-3 text-caption"
                data-testid="validation-sq-trust-tiers"
              >
                {strategyContext.byTrustTier.map((row) => (
                  <li key={row.trust_tier}>
                    {row.trust_tier}: {row.count == null ? "—" : row.count}
                  </li>
                ))}
              </ul>
            ) : null}
            {strategyContext.warnings.length ? (
              <ul
                className="space-y-1 text-caption text-amber-500/90"
                data-testid="validation-sq-warnings"
              >
                {strategyContext.warnings.map((warning) => (
                  <li key={warning.code}>{warning.message}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </ChartFrame>
    </div>
  );
}
