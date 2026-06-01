"use client";

import { useCallback } from "react";

import { AuditEventCard } from "@/components/AuditEventCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function AuditPage() {
  const loader = useCallback(() => api.audit.events({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Audit</h1>
        <p className="text-sm text-zinc-400">Redacted audit trail for compliance-style review.</p>
      </div>
      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      <div className="grid gap-4">
        {data?.items.length ? (
          data.items.map((event) => <AuditEventCard key={event.event_id} event={event} />)
        ) : (
          <EmptyState title="No audit events" />
        )}
      </div>
    </div>
  );
}
