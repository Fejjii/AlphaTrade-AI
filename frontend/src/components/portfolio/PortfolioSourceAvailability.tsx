"use client";

import { useId, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type PortfolioSourceStatus = {
  name: string;
  available: boolean;
  error?: string | null;
  timestamp?: string | null;
  required?: boolean;
  coverage?: "complete" | "truncated" | "unknown" | null;
};

type PortfolioSourceAvailabilityProps = {
  sources: PortfolioSourceStatus[];
  onRetry?: () => void;
  limitations?: string[];
};

export function isPortfolioSourceFullyHealthy(source: PortfolioSourceStatus): boolean {
  return (
    source.available &&
    !source.error &&
    (source.coverage == null || source.coverage === "complete")
  );
}

function sourceBadgeLabel(source: PortfolioSourceStatus): string {
  if (!source.available) {
    return "Unavailable";
  }
  if (source.error || source.coverage === "truncated" || source.coverage === "unknown") {
    return "Partial";
  }
  return "Available";
}

function sourceBadgeVariant(source: PortfolioSourceStatus): "success" | "warning" {
  return isPortfolioSourceFullyHealthy(source) ? "success" : "warning";
}

export function PortfolioSourceAvailability({
  sources,
  onRetry,
  limitations = [],
}: PortfolioSourceAvailabilityProps) {
  const unavailable = sources.filter((source) => !source.available);
  const degraded = sources.filter((source) => !isPortfolioSourceFullyHealthy(source));
  const partialCoverage = sources.filter(
    (source) =>
      source.available &&
      (Boolean(source.error) ||
        source.coverage === "truncated" ||
        source.coverage === "unknown"),
  );
  const allFailed = sources.length > 0 && sources.every((source) => !source.available);
  const partial = degraded.length > 0 && !allFailed;
  const allFullyHealthy =
    sources.length > 0 && sources.every(isPortfolioSourceFullyHealthy) && limitations.length === 0;
  // Degraded coverage always stays open; only a fully healthy set is collapsed,
  // so progressive disclosure never hides a problem (FP2-124).
  const showDegradedDetail = !allFullyHealthy;
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const detailsVisible = showDegradedDetail || expanded;

  return (
    <section
      aria-labelledby="portfolio-source-availability-heading"
      data-testid="portfolio-source-availability"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2
            id="portfolio-source-availability-heading"
            className="text-lg font-semibold text-text-primary"
          >
            Source availability and coverage
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Failed sources never appear as zero balances or empty success. Missing timestamps mean
            freshness unavailable.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {showDegradedDetail ? null : (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="min-h-11"
              aria-expanded={expanded}
              aria-controls={detailsId}
              onClick={() => setExpanded((open) => !open)}
              data-testid="portfolio-sources-toggle"
            >
              {expanded ? "Hide source detail" : "Show source detail"}
            </Button>
          )}
          {onRetry && degraded.length > 0 ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="min-h-11"
              onClick={onRetry}
              data-testid="portfolio-sources-retry"
            >
              Retry sources
            </Button>
          ) : null}
        </div>
      </div>

      {allFullyHealthy ? (
        <p
          className="rounded-control border border-success-border bg-success-muted/40 px-3 py-2 text-sm text-success"
          data-testid="portfolio-sources-all-healthy"
        >
          All {sources.length} Portfolio sources available with complete coverage.
        </p>
      ) : null}

      {allFailed ? (
        <div
          role="alert"
          data-testid="portfolio-sources-all-failed"
          className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
        >
          All Portfolio sources are unavailable. Balances, positions, and risk allowance are
          suppressed.
        </div>
      ) : null}

      {partial ? (
        <div
          role="status"
          data-testid="portfolio-sources-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            {unavailable.length > 0
              ? `${unavailable.map((source) => source.name).join(", ")} unavailable. `
              : null}
            {partialCoverage.length > 0
              ? `${partialCoverage.map((source) => source.name).join(", ")} reporting partial or degraded coverage. `
              : null}
            Showing available sections only.
          </p>
        </div>
      ) : null}

      {limitations.length > 0 ? (
        <div
          role="status"
          data-testid="portfolio-coverage-limitations"
          className="rounded-control border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-secondary"
        >
          <p className="font-medium text-text-primary">Coverage limitations</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {detailsVisible ? (
      <ul id={detailsId} className="grid gap-2 sm:grid-cols-2" data-testid="portfolio-source-list">
        {sources.map((source) => (
          <li
            key={source.name}
            className="rounded-control border border-border-subtle px-3 py-2 text-sm"
            data-testid={`portfolio-source-${source.name.toLowerCase().replaceAll(" ", "-")}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium text-text-primary">{source.name}</span>
              <Badge variant={sourceBadgeVariant(source)} data-testid={`portfolio-source-badge-${source.name.toLowerCase().replaceAll(" ", "-")}`}>
                {sourceBadgeLabel(source)}
              </Badge>
            </div>
            {source.coverage ? (
              <p className="mt-1 text-caption text-text-muted" data-testid={`portfolio-source-coverage-${source.name.toLowerCase().replaceAll(" ", "-")}`}>
                Coverage: {source.coverage}
              </p>
            ) : null}
            {source.error ? (
              <p className="mt-1 text-caption text-text-muted" data-testid={`portfolio-source-error-${source.name.toLowerCase().replaceAll(" ", "-")}`}>
                {source.error}
              </p>
            ) : null}
            <p className="mt-1 text-caption text-text-muted">
              Freshness timestamp:{" "}
              {source.timestamp && Number.isFinite(Date.parse(source.timestamp))
                ? new Date(source.timestamp).toLocaleString()
                : "unavailable"}
            </p>
          </li>
        ))}
      </ul>
      ) : null}
    </section>
  );
}
