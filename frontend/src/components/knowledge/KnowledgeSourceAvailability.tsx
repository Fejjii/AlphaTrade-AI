import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type KnowledgeSourceStatus = {
  name: string;
  available: boolean;
  error?: string | null;
  timestamp?: string | null;
  required?: boolean;
};

type KnowledgeSourceAvailabilityProps = {
  sources: KnowledgeSourceStatus[];
  onRetry?: () => void;
  limitations?: string[];
};

export function KnowledgeSourceAvailability({
  sources,
  onRetry,
  limitations = [],
}: KnowledgeSourceAvailabilityProps) {
  const unavailable = sources.filter((source) => !source.available);
  const allFailed = sources.length > 0 && sources.every((source) => !source.available);
  const partial = unavailable.length > 0 && !allFailed;

  return (
    <section
      aria-labelledby="knowledge-source-availability-heading"
      data-testid="knowledge-source-availability"
      className="space-y-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2
            id="knowledge-source-availability-heading"
            className="text-lg font-semibold text-text-primary"
          >
            Source availability and limitations
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Failed knowledge sources never appear as empty libraries. Unavailable counts stay
            hidden.
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
          data-testid="knowledge-sources-all-failed"
          className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
        >
          All knowledge sources are unavailable. Counts and empty states are suppressed.
        </div>
      ) : null}

      {partial ? (
        <div
          role="status"
          data-testid="knowledge-sources-partial"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-3 py-2 text-sm text-warning"
        >
          <p className="font-medium">Partial data</p>
          <p className="mt-1">
            {unavailable.map((source) => source.name).join(", ")} unavailable. Showing available
            sections only.
          </p>
        </div>
      ) : null}

      {limitations.length > 0 ? (
        <div
          role="status"
          data-testid="knowledge-limitations"
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

      <ul className="grid gap-2 sm:grid-cols-2" data-testid="knowledge-source-list">
        {sources.map((source) => (
          <li
            key={source.name}
            className="rounded-control border border-border-subtle px-3 py-2 text-sm"
            data-testid={`knowledge-source-${source.name.toLowerCase().replaceAll(" ", "-")}`}
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
