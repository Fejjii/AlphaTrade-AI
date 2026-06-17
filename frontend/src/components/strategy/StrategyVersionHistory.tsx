"use client";

import type { UserStrategyVersion } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Props = {
  versions: UserStrategyVersion[];
};

export function StrategyVersionHistory({ versions }: Props) {
  const fromLessons = versions.filter((v) => v.lesson_source_metadata);

  if (fromLessons.length === 0) {
    return (
      <Card data-testid="strategy-version-history">
        <CardHeader>
          <CardTitle className="text-base">Version history</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-500">
          No strategy versions created from accepted lessons yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="strategy-version-history">
      <CardHeader>
        <CardTitle className="text-base">Versions from lessons</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {fromLessons.map((version) => {
          const meta = version.lesson_source_metadata!;
          return (
            <article
              key={version.id}
              className="rounded border border-zinc-800 p-3"
              data-testid={`version-from-lesson-${version.version}`}
            >
              <p className="font-medium text-zinc-100">v{version.version}</p>
              <ul className="mt-2 space-y-1 text-zinc-400">
                <li>Source lesson: {meta.lesson_id}</li>
                <li>Mistake type: {meta.mistake_type}</li>
                <li>Accepted lesson: {meta.accepted_lesson_text}</li>
                {meta.rule_update_summary ? (
                  <li>Rule update: {meta.rule_update_summary}</li>
                ) : null}
                <li>Created: {new Date(meta.created_at).toLocaleString()}</li>
                {meta.reviewer_notes ? <li>Reviewer notes: {meta.reviewer_notes}</li> : null}
              </ul>
            </article>
          );
        })}
      </CardContent>
    </Card>
  );
}
