import { AlertTriangle, Ban, Clock, Inbox, Info, ShieldOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SkeletonCard } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  className,
}: {
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card border border-dashed border-border bg-surface-0/40 px-6 py-12 text-center",
        className,
      )}
      data-testid="empty-state"
    >
      <Inbox className="mb-3 h-8 w-8 text-text-disabled" aria-hidden="true" />
      <h3 className="text-base font-medium text-text-primary">{title}</h3>
      {description ? <p className="mt-2 max-w-md text-sm text-text-muted">{description}</p> : null}
    </div>
  );
}

export function LoadingState({
  label = "Loading…",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("space-y-3", className)}
      data-testid="loading-state"
    >
      <p className="text-sm text-text-muted">{label}</p>
      <SkeletonCard />
    </div>
  );
}

export function SuccessState({ message, className }: { message: string; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-card border border-success-border bg-success-muted px-6 py-4 text-center text-sm text-success",
        className,
      )}
    >
      {message}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      data-testid="error-state"
      className={cn(
        "rounded-card border border-danger-border bg-danger-muted px-6 py-8 text-center",
        className,
      )}
    >
      <AlertTriangle className="mx-auto mb-2 h-5 w-5 text-danger" aria-hidden="true" />
      <p className="text-sm text-danger">{message}</p>
      {onRetry ? (
        <Button type="button" variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function StaleState({
  message = "Data may be delayed or stale.",
  ageLabel,
  className,
}: {
  message?: string;
  ageLabel?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      data-testid="stale-state"
      className={cn(
        "rounded-card border border-stale-border bg-stale-muted px-4 py-3 text-sm text-stale",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <Clock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-medium">Stale data{ageLabel ? ` · ${ageLabel}` : ""}</p>
          <p className="mt-1 text-text-secondary">{message}</p>
        </div>
      </div>
    </div>
  );
}

/**
 * Neutral advisory for analytical / coverage / methodology limitations.
 * Not a freshness warning — do not use for stale/delayed market data.
 */
export function LimitationsState({
  title = "Limitations",
  message = "Some metrics carry explicit limitations — treat values as incomplete.",
  items,
  className,
}: {
  title?: string;
  message?: string;
  items?: string[];
  className?: string;
}) {
  return (
    <div
      role="status"
      data-testid="limitations-state"
      className={cn(
        "rounded-card border border-border bg-surface-1 px-4 py-3 text-sm text-text-primary",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" aria-hidden="true" />
        <div className="min-w-0 space-y-1">
          <p className="font-medium text-text-primary">{title}</p>
          <p className="text-text-secondary">{message}</p>
          {items && items.length > 0 ? (
            <ul className="mt-2 space-y-1 text-caption text-text-secondary">
              {items.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function BlockedState({
  message,
  className,
}: {
  message: string;
  className?: string;
}) {
  return (
    <div
      role="alert"
      data-testid="blocked-state"
      className={cn(
        "rounded-card border border-blocked-border bg-blocked-muted px-4 py-3 text-sm",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <Ban className="mt-0.5 h-4 w-4 shrink-0 text-blocked" aria-hidden="true" />
        <div>
          <p className="font-semibold uppercase tracking-wide text-blocked">Blocked</p>
          <p className="mt-1 text-text-primary">{message}</p>
        </div>
      </div>
    </div>
  );
}

export function UnavailableState({
  message = "This surface is temporarily unavailable.",
  onRetry,
  className,
}: {
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="status"
      data-testid="unavailable-state"
      className={cn(
        "rounded-card border border-border bg-surface-1 px-6 py-8 text-center",
        className,
      )}
    >
      <ShieldOff className="mx-auto mb-2 h-5 w-5 text-text-muted" aria-hidden="true" />
      <p className="text-sm text-text-secondary">{message}</p>
      {onRetry ? (
        <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
