"use client";

import Link from "next/link";
import { useCallback } from "react";

import { parseStoredSourceUri } from "./knowledgeDisplay";
import { resolveLessonRelationships } from "@/components/lessons/lessonDisplay";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { LessonCandidate, RagDocument } from "@/lib/api/types";

function LessonContext({ id }: { id: string }) {
  const loader = useCallback(() => api.lessons.getCandidate(id), [id]);
  const { data, loading, error, reload } = useAsyncData(loader, [id]);
  if (loading)
    return (
      <p role="status" className="text-sm text-text-muted">
        Loading related lesson…
      </p>
    );
  if (error)
    return (
      <p role="alert" className="text-sm text-danger">
        Related lesson unavailable.{" "}
        <Button variant="outline" size="sm" onClick={() => void reload()}>
          Retry lesson
        </Button>
      </p>
    );
  if (!data) return null;
  return (
    <div className="space-y-2 text-sm">
      <p className="whitespace-pre-wrap break-words text-text-secondary">
        {data.lesson_text}
      </p>
      <p className="text-text-muted">
        Lesson status: {data.status.replace(/_/g, " ")}
      </p>
      <ul className="space-y-1">
        {resolveLessonRelationships(data)
          .filter((link) => link.href)
          .map((link) => (
            <li key={link.kind}>
              <Link
                href={link.href!}
                className="inline-flex min-h-11 items-center underline"
              >
                {link.label}
              </Link>
            </li>
          ))}
      </ul>
    </div>
  );
}

function RelatedLessons({
  document,
  kind,
  id,
}: {
  document: RagDocument;
  kind: "journal" | "strategy";
  id: string;
}) {
  const loader = useCallback(
    () => api.lessons.listCandidates({ status: "accepted" }),
    [],
  );
  const { data, loading, error, reload } = useAsyncData(loader, [document.id]);
  if (loading)
    return (
      <p role="status" className="text-sm text-text-muted">
        Loading related lessons…
      </p>
    );
  if (error)
    return (
      <p role="alert" className="text-sm text-danger">
        Related lessons unavailable.{" "}
        <Button variant="outline" size="sm" onClick={() => void reload()}>
          Retry lessons
        </Button>
      </p>
    );
  const lessons =
    data?.items.filter((lesson: LessonCandidate) =>
      kind === "strategy"
        ? lesson.related_strategy_id === id
        : lesson.related_journal_entry_id === id,
    ) ?? [];
  return (
    <div className="space-y-2 text-sm">
      <h3 className="font-medium text-text-primary">Related lessons</h3>
      {!lessons.length ? (
        <p className="text-text-muted">
          No related lessons in the loaded records.
        </p>
      ) : (
        <ul className="space-y-3">
          {lessons.map((lesson) => (
            <li key={lesson.id} className="space-y-1">
              <Link
                href={`/lessons?candidate=${encodeURIComponent(lesson.id)}`}
                className="inline-flex min-h-11 items-center break-words underline"
              >
                {lesson.lesson_text}
              </Link>
              {lesson.related_journal_entry_id ? (
                <Link
                  href={`/journal?entry=${encodeURIComponent(lesson.related_journal_entry_id)}`}
                  className="flex min-h-11 items-center underline"
                >
                  Related journal entry
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {data && data.items.length < data.total ? (
        <p className="text-text-muted">
          Checked {data.items.length} of {data.total} accepted lessons.{" "}
          <Link href="/lessons" className="underline">
            Browse all lessons
          </Link>
        </p>
      ) : null}
    </div>
  );
}

/** Typed canonical references only: strategy tags and trade IDs are never entry IDs. */
export function KnowledgeRelatedContext({
  document,
}: {
  document: RagDocument;
}) {
  const source = parseStoredSourceUri(document.source_uri);
  if (!source.id || !source.kind) return null;
  if (source.kind === "lesson")
    return <LessonContext key={source.id} id={source.id} />;
  return (
    <RelatedLessons
      key={document.id}
      document={document}
      kind={source.kind}
      id={source.id}
    />
  );
}
