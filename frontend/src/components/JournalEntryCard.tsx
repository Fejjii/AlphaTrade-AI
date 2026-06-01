import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { JournalEntry } from "@/lib/api/types";
import { formatDate, truncate } from "@/lib/utils";

export function JournalEntryCard({ entry }: { entry: JournalEntry }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {entry.symbol} · {entry.direction.toUpperCase()}
          </CardTitle>
          <StatusBadge label={entry.result} tone="info" />
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-zinc-300">
        <p>{truncate(entry.entry_rationale, 220)}</p>
        {entry.lessons ? <p className="text-zinc-400">Lesson: {truncate(entry.lessons, 160)}</p> : null}
        <p className="text-zinc-500">{formatDate(entry.created_at)}</p>
      </CardContent>
    </Card>
  );
}
