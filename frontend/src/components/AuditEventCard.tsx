import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AuditRecord } from "@/lib/api/types";
import { formatDate, truncate } from "@/lib/utils";

export function AuditEventCard({ event }: { event: AuditRecord }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm">{event.event_type}</CardTitle>
          <StatusBadge
            label={event.severity}
            tone={event.severity === "critical" || event.severity === "error" ? "blocked" : "info"}
          />
        </div>
      </CardHeader>
      <CardContent className="min-w-0 space-y-2 text-sm text-zinc-300">
        <div
          className="grid min-w-0 gap-1 text-zinc-400 sm:grid-cols-2"
          data-testid="audit-event-identifiers"
        >
          <span className="min-w-0 break-all">Actor: {event.actor_type ?? "system"}</span>
          <span className="min-w-0 break-all">Result: {event.result}</span>
          <span className="min-w-0 break-all" data-testid="audit-event-request-id">
            Request: {event.request_id}
          </span>
          <span className="min-w-0 break-all" data-testid="audit-event-resource-id">
            Resource: {event.resource_id ?? "—"}
          </span>
          <span className="min-w-0 break-all">Action: {event.action}</span>
          <span className="min-w-0 break-all">{formatDate(event.timestamp)}</span>
        </div>
        {Object.keys(event.redacted_metadata).length > 0 ? (
          <pre
            className="max-w-full min-w-0 overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-zinc-950 p-3 text-xs text-zinc-400"
            data-testid="audit-event-metadata"
          >
            {truncate(JSON.stringify(event.redacted_metadata, null, 2), 500)}
          </pre>
        ) : null}
      </CardContent>
    </Card>
  );
}
