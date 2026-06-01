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
      <CardContent className="space-y-2 text-sm text-zinc-300">
        <div className="grid gap-1 text-zinc-400 sm:grid-cols-2">
          <span>Actor: {event.actor_type ?? "system"}</span>
          <span>Result: {event.result}</span>
          <span>Request: {truncate(event.request_id, 24)}</span>
          <span>Resource: {event.resource_id ?? "—"}</span>
          <span>Action: {event.action}</span>
          <span>{formatDate(event.timestamp)}</span>
        </div>
        {Object.keys(event.redacted_metadata).length > 0 ? (
          <pre className="overflow-x-auto rounded-lg bg-zinc-950 p-3 text-xs text-zinc-400">
            {truncate(JSON.stringify(event.redacted_metadata, null, 2), 500)}
          </pre>
        ) : null}
      </CardContent>
    </Card>
  );
}
