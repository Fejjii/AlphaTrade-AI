import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { formatTimestamp } from "@/components/validate/validationDisplay";
import type { ValidationStageModel } from "@/components/validate/types";
import { cn } from "@/lib/utils";

type ValidationStageProps = {
  stage: ValidationStageModel;
  index: number;
  compact?: boolean;
};

export function ValidationStage({ stage, index, compact = false }: ValidationStageProps) {
  const countLabel = stage.count == null ? "unavailable" : String(stage.count);
  const timestampLabel = formatTimestamp(stage.timestamp);

  return (
    <article
      data-testid={`validation-stage-${stage.id}`}
      aria-labelledby={`validation-stage-${stage.id}-title`}
      className={cn(
        "rounded-control border border-border-subtle bg-surface-0/40 px-4 py-3",
        !stage.available && "border-warning-border bg-warning-muted/20",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-caption text-text-muted">Stage {index + 1}</p>
          <h3
            id={`validation-stage-${stage.id}-title`}
            className="text-sm font-semibold text-text-primary"
          >
            {stage.name}
          </h3>
          {!compact ? (
            <p className="mt-1 text-sm text-text-secondary">{stage.purpose}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge
            variant={stage.available ? "muted" : "warning"}
            data-testid={`validation-stage-count-${stage.id}`}
          >
            Count: {countLabel}
          </Badge>
          <Badge variant="muted">{stage.statusLabel}</Badge>
        </div>
      </div>

      <dl className="mt-3 grid gap-2 text-caption text-text-muted sm:grid-cols-2">
        <div>
          <dt className="font-medium text-text-secondary">Next action</dt>
          <dd className="mt-0.5 text-text-primary">{stage.nextAction}</dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Blocker / missing evidence</dt>
          <dd className="mt-0.5 text-text-primary">
            {stage.blocker ?? (stage.available ? "None reported" : "Source unavailable")}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Timestamp</dt>
          <dd className="mt-0.5 text-text-primary">
            {timestampLabel ?? "unavailable"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-text-secondary">Detail route</dt>
          <dd className="mt-0.5">
            <Link
              href={stage.href}
              className="text-text-primary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              data-testid={`validation-stage-link-${stage.id}`}
            >
              Open {stage.name.toLowerCase()} list
            </Link>
          </dd>
        </div>
      </dl>
    </article>
  );
}
