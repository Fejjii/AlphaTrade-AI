import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

export function SettingsReadout({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-text-muted">{label}</dt>
          <dd className="mt-1 break-words text-text-primary">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SettingsUnavailable({
  label,
  loading,
  onRetry,
}: {
  label: string;
  loading: boolean;
  onRetry?: () => void;
}) {
  return (
    <div role="status" className="space-y-2 text-sm text-text-muted">
      <p>
        {loading ? `Loading ${label.toLowerCase()}…` : `${label} unavailable.`}
      </p>
      {!loading && onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Retry {label.toLowerCase()}
        </Button>
      ) : null}
    </div>
  );
}
