"use client";

import Link from "next/link";
import { useState } from "react";

import { journalEntryHref } from "@/components/journal/journalContext";
import {
  AGENT_REFLECTION_CONTRACT,
  journalMistakes,
} from "@/components/journal/trader-journal";
import { EmptyState, UnavailableState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataNumber } from "@/components/ui/data-number";
import { Input, Label, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import type { SafetyPostureDisplay } from "@/components/workflows/safetyPostureDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import {
  formatDateTime,
  formatMonetary,
  humanizeToken,
  UNAVAILABLE,
} from "@/lib/format";
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

function Outcome({ result }: { result: string | null | undefined }) {
  return (
    <Badge
      variant={
        result === "win" ? "success" : result === "loss" ? "danger" : "muted"
      }
    >
      {result ? humanizeToken(result) : "Outcome unavailable"}
    </Badge>
  );
}

export function TraderJournalView({
  data,
  posture,
  onRetry,
  refreshing = false,
}: {
  data: TraderJournalData;
  posture?: SafetyPostureDisplay;
  onRetry?: () => void;
  refreshing?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [outcome, setOutcome] = useState("");
  const trades =
    data.trades.available && data.trades.data ? data.trades.data.items : null;
  const entries =
    data.entries.available && data.entries.data
      ? data.entries.data.items
      : null;
  const lessons =
    data.lessons.available && data.lessons.data
      ? data.lessons.data.items
      : null;
  const prompts =
    data.coaching.available && data.coaching.data
      ? data.coaching.data.items
      : null;
  const query = search.trim().toLowerCase();
  const filteredTrades = trades?.filter(
    (trade) =>
      (!outcome || trade.result === outcome) &&
      [trade.symbol, trade.strategy_label, trade.thesis].some((value) =>
        value?.toLowerCase().includes(query),
      ),
  );
  const filteredEntries = entries?.filter(
    (entry) =>
      (!outcome || entry.result === outcome) &&
      [
        entry.symbol,
        entry.entry_rationale,
        entry.lessons,
        ...entry.mistakes,
      ].some((value) => value?.toLowerCase().includes(query)),
  );
  const failed = [
    trades == null ? "Trades" : null,
    entries == null ? "Journal entries" : null,
    lessons == null ? "Lessons" : null,
    prompts == null ? "Coaching prompts" : null,
  ].filter(Boolean);

  return (
    <div
      className="space-y-5 [&_input]:text-base [&_select]:text-base lg:[&_input]:text-sm lg:[&_select]:text-sm"
      data-testid="trader-journal"
    >
      <PageHeader
        title="Journal"
        description="Review the trade. Understand the decision. Keep the lesson."
        meta={<PaperModeIndicator active={posture?.paperConfirmed ?? false} />}
        actions={
          <Link
            href="/journal?view=record"
            className="inline-flex min-h-11 items-center rounded-control border border-accent-border bg-accent-muted px-4 text-sm font-medium text-accent"
          >
            Record a trade
          </Link>
        }
      />
      {posture?.conflictMessage ? (
        <p role="alert" className="text-sm text-danger">
          {posture.conflictMessage}
        </p>
      ) : null}
      <nav
        aria-label="Journal review"
        className="flex flex-wrap gap-2 border-b border-border-subtle pb-3 text-sm"
      >
        <Link
          href="/journal"
          aria-current="page"
          className="inline-flex min-h-11 items-center rounded-control bg-surface-2 px-3 font-medium"
        >
          Review
        </Link>
        <Link
          href="/journal/statistics"
          className="inline-flex min-h-11 items-center px-3 text-text-secondary hover:text-text-primary"
        >
          Statistics
        </Link>
        <Link
          href="/lessons"
          className="inline-flex min-h-11 items-center px-3 text-text-secondary hover:text-text-primary"
        >
          Lessons
        </Link>
        <Link
          href="/coaching"
          className="inline-flex min-h-11 items-center px-3 text-text-secondary hover:text-text-primary"
        >
          Coaching
        </Link>
      </nav>
      {failed.length ? (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-warning-border bg-warning-muted p-3 text-sm"
        >
          <p className="text-warning">
            Unavailable: {failed.join(", ")}. Review available records below.
          </p>
          {onRetry ? (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              disabled={refreshing}
            >
              Retry sources
            </Button>
          ) : null}
        </div>
      ) : null}
      {refreshing ? (
        <p role="status" className="text-sm text-text-secondary">
          Refreshing journal; showing the previous snapshot.
        </p>
      ) : null}
      <div className="grid gap-3 rounded-card border border-border-subtle bg-surface-1 p-4 sm:grid-cols-[minmax(0,1fr)_12rem]">
        <div className="space-y-2">
          <Label htmlFor="journal-review-search">Search recent records</Label>
          <Input
            id="journal-review-search"
            type="search"
            placeholder="Symbol, reasoning, or lesson…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="journal-review-outcome">Outcome</Label>
          <Select
            id="journal-review-outcome"
            value={outcome}
            onChange={(event) => setOutcome(event.target.value)}
          >
            <option value="">All outcomes</option>
            <option value="win">Win</option>
            <option value="loss">Loss</option>
            <option value="breakeven">Breakeven</option>
          </Select>
        </div>
        <p className="text-xs text-text-secondary sm:col-span-2">
          Filters apply to the loaded recent trades and entries. Statistics
          covers the closed-trade sample.
        </p>
      </div>
      <div className="grid items-start gap-4 xl:grid-cols-2">
        <Card data-testid="journal-trades">
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
            <CardTitle>Trades</CardTitle>
            <span className="text-xs text-text-secondary">
              {filteredTrades
                ? `${filteredTrades.length} of ${trades?.length} loaded`
                : "Unavailable"}
            </span>
          </CardHeader>
          <CardContent>
            {trades == null ? (
              <UnavailableState
                message="Trades unavailable"
                onRetry={onRetry}
                className="py-6"
              />
            ) : trades.length === 0 ? (
              <EmptyState
                title="No canonical trades yet."
                description="Recorded canonical trades will appear here with their thesis and outcome."
                className="py-8"
              />
            ) : filteredTrades?.length === 0 ? (
              <EmptyState
                title="No matching trades"
                description="Try another symbol or outcome in the recent records."
                className="py-8"
              />
            ) : (
              <ul className="space-y-3">
                {filteredTrades?.map((trade) => (
                  <li
                    key={trade.id}
                    className="min-w-0 rounded-control border border-border-subtle bg-surface-0/40 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="break-words text-sm font-semibold">
                        {trade.symbol} · {trade.direction}
                      </p>
                      <Outcome result={trade.result} />
                    </div>
                    <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
                      <p className="text-xs text-text-secondary">
                        {trade.timeframe || UNAVAILABLE} ·{" "}
                        {humanizeToken(trade.status)}
                      </p>
                      <p className="text-xs text-text-secondary">
                        Net PnL{" "}
                        <DataNumber value={formatMonetary(trade.net_pnl)} />
                      </p>
                    </div>
                    <p className="mt-3 break-words text-sm leading-relaxed text-text-primary">
                      {trade.thesis?.trim() || "No thesis recorded"}
                    </p>
                    <p className="mt-3 break-words text-xs text-text-secondary">
                      Strategy {trade.strategy_label?.trim() || UNAVAILABLE}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card data-testid="journal-entries">
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
            <CardTitle>Reasoning and outcomes</CardTitle>
            <span className="text-xs text-text-secondary">
              {filteredEntries
                ? `${filteredEntries.length} of ${entries?.length} loaded`
                : "Unavailable"}
            </span>
          </CardHeader>
          <CardContent>
            {entries == null ? (
              <UnavailableState
                message="Journal entries unavailable"
                onRetry={onRetry}
                className="py-6"
              />
            ) : entries.length === 0 ? (
              <EmptyState
                title="No journal entries yet."
                description="Record your reasoning, mistakes, and lesson while the trade is fresh."
                className="py-8"
              />
            ) : filteredEntries?.length === 0 ? (
              <EmptyState
                title="No matching entries"
                description="Try another phrase or outcome in the recent records."
                className="py-8"
              />
            ) : (
              <ul className="space-y-3">
                {filteredEntries?.map((entry) => (
                  <li
                    key={entry.id}
                    className="min-w-0 rounded-control border border-border-subtle bg-surface-0/40 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="break-words text-sm font-semibold">
                        {entry.symbol} · {entry.direction}
                      </p>
                      <Outcome result={entry.result} />
                    </div>
                    <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
                      <p className="text-xs text-text-secondary">
                        {formatDateTime(entry.created_at)}
                      </p>
                      <p className="text-xs text-text-secondary">
                        Recorded PnL{" "}
                        <DataNumber value={formatMonetary(entry.pnl)} />
                      </p>
                    </div>
                    <p className="mt-3 break-words text-sm leading-relaxed text-text-primary">
                      {entry.entry_rationale?.trim() || "No reasoning recorded"}
                    </p>
                    <dl className="mt-3 space-y-2 border-t border-border-subtle pt-3 text-sm">
                      <div>
                        <dt className="text-xs text-text-secondary">
                          Mistakes
                        </dt>
                        <dd className="mt-1 break-words">
                          {journalMistakes(entry.mistakes)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-text-secondary">Lesson</dt>
                        <dd className="mt-1 break-words text-text-primary">
                          {entry.lessons?.trim() || "No lesson recorded"}
                        </dd>
                      </div>
                    </dl>
                    <p className="mt-3 break-words text-xs text-text-secondary">
                      Strategy: {entry.strategy_id?.trim() || UNAVAILABLE}
                    </p>
                    <Link
                      href={journalEntryHref(entry.id)}
                      className="mt-2 inline-flex min-h-11 items-center text-sm text-accent hover:underline"
                    >
                      Review entry
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card data-testid="journal-lessons">
          <CardHeader>
            <CardTitle>Lessons</CardTitle>
          </CardHeader>
          <CardContent>
            {lessons == null ? (
              <UnavailableState
                message="Lessons unavailable"
                onRetry={onRetry}
                className="py-6"
              />
            ) : lessons.length === 0 ? (
              <EmptyState
                title="No lesson candidates."
                description="Capture a lesson from a journal review to build your playbook."
                className="py-8"
              />
            ) : (
              <ul className="space-y-3">
                {lessons.map((lesson) => (
                  <li
                    key={lesson.id}
                    className="border-b border-border-subtle pb-3 last:border-b-0"
                  >
                    <p className="break-words text-sm leading-relaxed">
                      {lesson.lesson_text}
                    </p>
                    <p className="mt-2 break-words text-xs text-text-secondary">
                      {humanizeToken(lesson.mistake_type)} ·{" "}
                      {humanizeToken(lesson.status)}
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
            <p className="text-xs text-text-secondary">
              Generated coaching prompts. These are not stored Agent
              reflections.
            </p>
            {prompts == null ? (
              <UnavailableState
                message="Coaching prompts unavailable"
                onRetry={onRetry}
                className="py-6"
              />
            ) : prompts.length === 0 ? (
              <EmptyState
                title="No coaching prompts."
                description="Generated prompts will appear here when available."
                className="py-8"
              />
            ) : (
              <ul className="space-y-2">
                {prompts.map((prompt) => (
                  <li
                    key={prompt.signature}
                    className="rounded-control border border-border-subtle p-3 text-sm leading-relaxed text-text-primary"
                  >
                    {prompt.prompt_text}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
      <details
        className="rounded-control border border-border-subtle p-4"
        data-testid="journal-agent-reflections"
      >
        <summary className="cursor-pointer text-sm font-medium text-text-secondary">
          Agent reflections · unavailable
        </summary>
        <p className="mt-3 text-sm text-text-secondary">
          {AGENT_REFLECTION_CONTRACT}
        </p>
      </details>
    </div>
  );
}
