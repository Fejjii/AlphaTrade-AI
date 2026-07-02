"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LessonCandidate } from "@/lib/api/types";

type Props = {
  lesson: LessonCandidate;
  onAccept?: () => void;
  onReject?: () => void;
  busy?: boolean;
};

function formatSourceType(sourceType: string): string {
  return sourceType.replace(/_/g, " ");
}

export function LessonCandidateCard({ lesson, onAccept, onReject, busy }: Props) {
  const isPending = lesson.status === "pending_review";
  const isCoaching = lesson.source_type === "coaching";

  return (
    <Card data-testid="lesson-candidate-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-base capitalize">{lesson.mistake_type.replace(/_/g, " ")}</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            {isCoaching ? (
              <Badge variant="info" data-testid="lesson-source-coaching">
                Coaching
              </Badge>
            ) : (
              <span className="text-xs text-zinc-500" data-testid="lesson-source-label">
                {formatSourceType(lesson.source_type)}
              </span>
            )}
            <Badge variant="muted">{lesson.severity}</Badge>
          </div>
        </div>
        <p className="text-xs text-zinc-500">
          {lesson.confidence ? `confidence ${lesson.confidence}` : "confidence n/a"}
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p data-testid="lesson-text">{lesson.lesson_text}</p>
        {lesson.related_strategy_id ? (
          <p className="text-zinc-400">
            Strategy:{" "}
            <Link href={`/strategy-lab/${lesson.related_strategy_id}`} className="underline">
              {lesson.related_strategy_id.slice(0, 8)}…
            </Link>
          </p>
        ) : null}
        {lesson.related_journal_entry_id ? (
          <p className="text-zinc-400">
            Journal:{" "}
            <Link href={`/journal?entry=${lesson.related_journal_entry_id}`} className="underline">
              View entry
            </Link>
          </p>
        ) : null}
        {lesson.proposed_rule_update?.summary ? (
          <div className="rounded border border-zinc-800 p-2 text-zinc-400">
            <p className="font-medium text-zinc-200">Proposed rule update</p>
            <p>{lesson.proposed_rule_update.summary}</p>
          </div>
        ) : null}
        {isPending && onAccept && onReject ? (
          <div className="flex flex-wrap gap-2" data-testid="lesson-actions">
            <button
              type="button"
              disabled={busy}
              className="rounded-lg bg-emerald-700/80 px-3 py-1.5 text-white disabled:opacity-50"
              data-testid="accept-lesson-btn"
              onClick={onAccept}
            >
              Accept
            </button>
            <button
              type="button"
              disabled={busy}
              className="rounded-lg border border-zinc-600 px-3 py-1.5 disabled:opacity-50"
              data-testid="reject-lesson-btn"
              onClick={onReject}
            >
              Reject
            </button>
          </div>
        ) : (
          <p className="text-xs uppercase tracking-wide text-zinc-500">{lesson.status}</p>
        )}
      </CardContent>
    </Card>
  );
}
