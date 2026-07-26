import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type ValidationSourceStatus = {
  name: string;
  available: boolean;
  error?: string | null;
  timestamp?: string | null;
  required?: boolean;
};

type ValidationSourceAvailabilityProps = {
  sources: ValidationSourceStatus[];
  onRetry?: () => void;
};

export function ValidationSourceAvailability({
  sources,
  onRetry,
}: ValidationSourceAvailabilityProps) {
  const unavailable = sources.filter((s) => !s.available);
  const allFailed = sources.length > 0 && sources.every((s) => !s.available);
  const partial = unavailable.length > 0 && !allFailed;

  return (
    <section
      aria-labelledby="validation-source-availability-heading"
      data-testid="validation-source-availability"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2
            id="validation-source-availability-heading"
            className="text-lg font-semibold text-text-primary"
          >
            Source availability
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Failed sources never appear as empty success. Unavailable counts stay hidden.
          </p>
        </div>
        {onRetry && unavailable.length > 0 ? (
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            Retry sources
          </Button>
        ) : null}
      </div>

      {allFailed ? (
        <div
          role="alert"
          data-testid="validation-sources-all-failed"
          className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
        >
          All Validate sources are unavailable. Counts and empty states are suppressed.
        </div>
      ) : null}

      {partial ? (
        <div
          role="status"
          data-testid="validation-sources-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          Partial source coverage. Page-level Live freshness is not claimed while any required
          source is stale or unavailable.
        </div>
      ) : null}

      <ul className="grid gap-2 sm:grid-cols-2" data-testid="validation-source-list">
        {sources.map((source) => (
          <li
            key={source.name}
            className="rounded-control border border-border-subtle px-3 py-2 text-sm"
            data-testid={`validation-source-${source.name.toLowerCase().replaceAll(" ", "-")}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium text-text-primary">{source.name}</span>
              <Badge variant={source.available ? "success" : "warning"}>
                {source.available ? "Available" : "Unavailable"}
              </Badge>
            </div>
            {!source.available && source.error ? (
              <p className="mt-1 text-caption text-text-muted">{source.error}</p>
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
    </section>
  );
}
