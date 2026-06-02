import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { JournalEntry } from "@/lib/api/types";
import { SETUP_TYPE_OPTIONS } from "@/lib/setup-types";
import { formatDate, truncate } from "@/lib/utils";

function setupLabel(value: string | null | undefined) {
  if (!value) return null;
  return SETUP_TYPE_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

export function JournalEntryCard({ entry }: { entry: JournalEntry }) {
  const setup = setupLabel(entry.strategy_id ?? undefined);
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            {entry.symbol} · {entry.direction.toUpperCase()}
            {setup ? ` · ${setup}` : ""}
          </CardTitle>
          <div className="flex gap-2">
            <StatusBadge label={entry.result} tone="info" />
            {entry.rag_synced ? (
              <StatusBadge label="RAG synced" tone="ok" />
            ) : (
              <StatusBadge label="RAG pending" tone="pending" />
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-zinc-300">
        <p>{truncate(entry.entry_rationale, 220)}</p>
        {entry.lessons ? <p className="text-zinc-400">Lesson: {truncate(entry.lessons, 160)}</p> : null}
        {entry.improvement_rule ? (
          <p className="text-zinc-400">Rule: {truncate(entry.improvement_rule, 120)}</p>
        ) : null}
        {entry.mistakes.length ? (
          <p className="text-zinc-500">Mistakes: {entry.mistakes.join(", ")}</p>
        ) : null}
        {entry.emotions.length ? (
          <p className="text-zinc-500">Emotions: {entry.emotions.join(", ")}</p>
        ) : null}
        <p className="text-zinc-500">{formatDate(entry.created_at)}</p>
      </CardContent>
    </Card>
  );
}
