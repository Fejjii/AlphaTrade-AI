"use client";

import { useId, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  ObservationSourceState,
  ResultSourceState,
} from "@/components/validate/sessionExtras";
import type {
  PaperValidationSessionObservationItem,
  PaperValidationSessionResultItem,
} from "@/lib/api/types";
import {
  excursionAvailabilityLabel,
  formatTimestamp,
  outcomeStatusLabel,
} from "@/components/validate/validationDisplay";

type OutcomeSummaryProps = {
  observations: PaperValidationSessionObservationItem[] | null;
  observationsState: ObservationSourceState;
  /** When true, observations remain visible but the source is refreshing. */
  observationsRefreshing?: boolean;
  result: PaperValidationSessionResultItem | null;
  resultState: ResultSourceState;
  resultRetrying?: boolean;
  resultError?: string | null;
  onRetryExtras?: () => void;
};

export function OutcomeSummary({
  observations,
  observationsState,
  observationsRefreshing = false,
  result,
  resultState,
  resultRetrying = false,
  resultError = null,
  onRetryExtras,
}: OutcomeSummaryProps) {
  const detailsId = useId();
  const [expanded, setExpanded] = useState(false);
  const observationsLoading = observationsState === "loading";
  const observationsUnavailable = observationsState === "unavailable";
  const observationsAvailable = observationsState === "available";
  const resultLoading = resultState === "loading";
  const resultUnavailable = resultState === "unavailable";
  const resultNotRecorded = resultState === "confirmed_not_recorded";
  const latest = observationsAvailable
    ? (observations ?? []).slice().sort((a, b) => {
        const aMs = Date.parse(a.observed_at ?? a.created_at);
        const bMs = Date.parse(b.observed_at ?? b.created_at);
        return (Number.isFinite(bMs) ? bMs : 0) - (Number.isFinite(aMs) ? aMs : 0);
      })[0]
    : undefined;
  const observationCount = observationsAvailable ? (observations?.length ?? 0) : null;
  const statusLabel = outcomeStatusLabel(result, { resultState });

  return (
    <section
      aria-labelledby="outcome-summary-heading"
      data-testid="outcome-summary"
      className="space-y-3 rounded-control border border-border-subtle bg-surface-0/40 px-4 py-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="outcome-summary-heading" className="text-base font-semibold text-text-primary">
            Observations and outcomes
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            High-level summary first. Detailed observations use progressive disclosure.
          </p>
        </div>
        <Badge variant={result ? "info" : "muted"}>{statusLabel}</Badge>
      </div>

      {observationsLoading ? (
        <p role="status" className="text-sm text-text-muted" data-testid="outcome-obs-loading">
          Loading observations…
        </p>
      ) : null}
      {observationsRefreshing ? (
        <p role="status" className="text-sm text-text-muted" data-testid="outcome-obs-refreshing">
          Refreshing observations…
        </p>
      ) : null}
      {observationsUnavailable ? (
        <p role="status" className="text-sm text-warning" data-testid="outcome-obs-unavailable">
          Observation source unavailable.
        </p>
      ) : null}

      {resultLoading ? (
        <p role="status" className="text-sm text-text-muted" data-testid="outcome-result-loading">
          {resultRetrying ? "Retrying outcome source…" : "Loading outcome source…"}
        </p>
      ) : null}
      {resultUnavailable ? (
        <p role="status" className="text-sm text-warning" data-testid="outcome-result-unavailable">
          Outcome source unavailable
          {resultError ? `: ${resultError}` : "."} Do not treat this as confirmed not recorded.
        </p>
      ) : null}
      {resultNotRecorded && !result ? (
        <p role="status" className="text-sm text-text-muted" data-testid="outcome-not-recorded">
          Outcome not recorded.
        </p>
      ) : null}

      {onRetryExtras && (observationsUnavailable || resultUnavailable) ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onRetryExtras}
          data-testid="outcome-retry-extras"
        >
          Retry observations and outcome
        </Button>
      ) : null}

      <dl className="grid gap-2 text-sm text-text-secondary sm:grid-cols-2">
        <div>
          <dt className="text-caption text-text-muted">Observation count</dt>
          <dd className="font-medium text-text-primary" data-testid="outcome-observation-count">
            {observationsLoading
              ? "…"
              : observationCount == null
                ? "unavailable"
                : String(observationCount)}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-text-muted">Latest observation</dt>
          <dd className="font-medium text-text-primary" data-testid="outcome-latest-observation">
            {latest
              ? `${latest.observation_kind.replaceAll("_", " ")} · ${formatTimestamp(latest.observed_at ?? latest.created_at) ?? "unavailable"}`
              : observationsLoading
                ? "…"
                : observationsAvailable
                  ? "None recorded"
                  : "unavailable"}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-text-muted">MFE</dt>
          <dd className="font-medium text-text-primary" data-testid="outcome-mfe">
            {excursionAvailabilityLabel()}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-text-muted">MAE</dt>
          <dd className="font-medium text-text-primary" data-testid="outcome-mae">
            {excursionAvailabilityLabel()}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-text-muted">Success / failure</dt>
          <dd className="font-medium text-text-primary" data-testid="outcome-success-failure">
            {result
              ? `success ${result.success_criteria_met.replaceAll("_", " ")} · failure ${result.failure_criteria_met.replaceAll("_", " ")}`
              : resultLoading
                ? "…"
                : resultUnavailable
                  ? "unavailable"
                  : resultNotRecorded
                    ? "not recorded"
                    : "not recorded"}
          </dd>
        </div>
        <div>
          <dt className="text-caption text-text-muted">Discipline / rule compliance</dt>
          <dd className="font-medium text-text-primary" data-testid="outcome-discipline">
            {result
              ? result.discipline_assessment.replaceAll("_", " ")
              : resultLoading
                ? "…"
                : resultUnavailable
                  ? "unavailable"
                  : "not recorded"}
          </dd>
        </div>
      </dl>

      <div
        className="rounded-control border border-border-subtle px-3 py-2 text-caption text-text-muted"
        data-testid="outcome-limitations"
      >
        Limitations: paper observation record only. No exchange fill reconstruction. MFE/MAE are not
        invented in the frontend. Outcome recording requires typed confirmation.
      </div>

      <Button
        type="button"
        size="sm"
        variant="outline"
        aria-expanded={expanded}
        aria-controls={detailsId}
        onClick={() => setExpanded((value) => !value)}
        data-testid="outcome-toggle-details"
      >
        {expanded ? "Hide observation details" : "Show observation details"}
      </Button>

      <div
        id={detailsId}
        hidden={!expanded}
        data-testid="outcome-details"
        className="space-y-2"
      >
        {observationsLoading ? (
          <p className="text-sm text-text-muted">Loading observation details…</p>
        ) : observationsUnavailable ? (
          <p className="text-sm text-warning">Cannot expand — observation source unavailable.</p>
        ) : (observations?.length ?? 0) === 0 ? (
          <p className="text-sm text-text-muted">No observations recorded for this session.</p>
        ) : (
          <ul className="space-y-2">
            {(observations ?? []).map((obs) => (
              <li
                key={obs.observation_id}
                className="rounded-control border border-border-subtle px-3 py-2 text-sm"
                data-testid={`outcome-obs-${obs.observation_id}`}
              >
                <p className="font-medium text-text-primary">
                  {obs.observation_kind.replaceAll("_", " ")}
                </p>
                <p className="text-caption text-text-muted">
                  {formatTimestamp(obs.observed_at ?? obs.created_at) ?? "unavailable"}
                  {obs.observed_price != null ? ` · price ${obs.observed_price}` : ""}
                </p>
                {obs.note ? <p className="mt-1 text-text-secondary">{obs.note}</p> : null}
              </li>
            ))}
          </ul>
        )}
        {result ? (
          <div className="rounded-control border border-border-subtle px-3 py-2 text-sm space-y-1">
            <p>
              Entry assessment:{" "}
              <span className="text-text-primary">
                {result.entry_assessment.replaceAll("_", " ")}
              </span>
            </p>
            {result.lessons ? <p>Lessons: {result.lessons}</p> : null}
            {result.success_criteria_notes ? (
              <p>Success notes: {result.success_criteria_notes}</p>
            ) : null}
            {result.failure_criteria_notes ? (
              <p>Failure notes: {result.failure_criteria_notes}</p>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
