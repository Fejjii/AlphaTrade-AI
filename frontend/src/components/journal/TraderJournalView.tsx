"use client";

import Link from "next/link";

import { AGENT_REFLECTION_CONTRACT, journalMistakes } from "@/components/journal/trader-journal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import type { SourceResult } from "@/components/workflows/sourceResult";
import { formatMonetary, UNAVAILABLE } from "@/lib/format";
import type {
  CanonicalJournalTradeListItem,
  CoachingPrompt,
  JournalEntry,
  LessonCandidate,
} from "@/lib/api/types";

export type TraderJournalData = {
  entries: SourceResult<{ items: JournalEntry[] }>;
  trades: SourceResult<{ items: CanonicalJournalTradeListItem[] }>;
  lessons: SourceResult<{ items: LessonCandidate[] }>;
  coaching: SourceResult<{ items: CoachingPrompt[] }>;
};

function Note({ children }: { children: string }) {
  return <p className="text-sm text-text-muted">{children}</p>;
}

export function TraderJournalView({ data }: { data: TraderJournalData }) {
  const trades = data.trades.available ? (data.trades.data?.items ?? []) : null;
  const entries = data.entries.available ? (data.entries.data?.items ?? []) : null;
  const lessons = data.lessons.available ? (data.lessons.data?.items ?? []) : null;
  const prompts = data.coaching.available ? (data.coaching.data?.items ?? []) : null;

  return (
    <div className="space-y-6" data-testid="trader-journal">
      <PageHeader
        title="Journal"
        description="Trades, reasoning, outcomes, and lessons. Paper records only."
        actions={
          <Link
            href="/journal?view=record"
            className="inline-flex h-10 items-center rounded-control border border-border px-4 text-sm text-text-primary"
          >
            Record a trade
          </Link>
        }
      />

      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/lessons" className="text-accent hover:underline">
          Lessons
        </Link>
        <Link href="/coaching" className="text-accent hover:underline">
          Coaching
        </Link>
      </div>

      <Card data-testid="journal-trades">
        <CardHeader>
          <CardTitle>Trades</CardTitle>
        </CardHeader>
        <CardContent>
          {trades == null ? (
            <Note>Trades unavailable</Note>
          ) : trades.length === 0 ? (
            <Note>No canonical trades yet.</Note>
          ) : (
            <ul>
              {trades.map((trade) => (
                <li
                  key={trade.id}
                  className="grid gap-1 border-b border-border-subtle py-3 text-sm last:border-b-0 sm:grid-cols-[minmax(0,1fr)_auto]"
                >
                  <div className="min-w-0">
                    <p className="text-text-primary">
                      {trade.symbol} · {trade.direction} · {trade.result || UNAVAILABLE}
                    </p>
                    <p className="text-text-secondary">{trade.thesis?.trim() || "No thesis recorded"}</p>
                    <p className="text-caption text-text-muted">
                      Strategy {trade.strategy_label?.trim() || UNAVAILABLE}
                    </p>
                  </div>
                  <p className="font-data text-text-secondary">{formatMonetary(trade.net_pnl)}</p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card data-testid="journal-entries">
        <CardHeader>
          <CardTitle>Reasoning and outcomes</CardTitle>
        </CardHeader>
        <CardContent>
          {entries == null ? (
            <Note>Journal entries unavailable</Note>
          ) : entries.length === 0 ? (
            <Note>No journal entries yet.</Note>
          ) : (
            <ul className="space-y-4">
              {entries.map((entry) => (
                <li key={entry.id} className="border-b border-border-subtle pb-4 last:border-b-0">
                  <p className="text-sm text-text-primary">
                    {entry.symbol} · {entry.direction} · {entry.result || UNAVAILABLE}
                  </p>
                  <p className="mt-1 text-sm text-text-secondary">{entry.entry_rationale}</p>
                  <p className="mt-1 font-data text-sm">{formatMonetary(entry.pnl)}</p>
                  <p className="mt-1 text-caption text-text-muted">
                    Mistakes: {journalMistakes(entry.mistakes)}
                  </p>
                  <p className="text-caption text-text-muted">
                    Lesson: {entry.lessons?.trim() || UNAVAILABLE}
                  </p>
                  <p className="text-caption text-text-muted">
                    Strategy: {entry.strategy_id?.trim() || UNAVAILABLE}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="journal-lessons">
          <CardHeader>
            <CardTitle>Lessons</CardTitle>
          </CardHeader>
          <CardContent>
            {lessons == null ? (
              <Note>Lessons unavailable</Note>
            ) : lessons.length === 0 ? (
              <Note>No lesson candidates.</Note>
            ) : (
              <ul className="space-y-3">
                {lessons.map((lesson) => (
                  <li key={lesson.id} className="text-sm">
                    <p className="text-text-primary">{lesson.lesson_text}</p>
                    <p className="text-caption text-text-muted">
                      {lesson.mistake_type} · {lesson.status}
                      {lesson.related_strategy_id
                        ? ` · strategy ${lesson.related_strategy_id}`
                        : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card data-testid="journal-coaching-prompts">
          <CardHeader>
            <CardTitle>Coaching prompts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-caption text-text-muted">
              Generated coaching prompts. These are not stored Agent reflections.
            </p>
            {prompts == null ? (
              <Note>Coaching prompts unavailable</Note>
            ) : prompts.length === 0 ? (
              <Note>No coaching prompts.</Note>
            ) : (
              <ul className="space-y-2">
                {prompts.map((prompt) => (
                  <li key={prompt.signature} className="text-sm text-text-secondary">
                    {prompt.prompt_text}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card data-testid="journal-agent-reflections">
        <CardHeader>
          <CardTitle>Agent reflections</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-muted">{AGENT_REFLECTION_CONTRACT}</p>
        </CardContent>
      </Card>
    </div>
  );
}
