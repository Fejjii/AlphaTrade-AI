import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataNumber } from "@/components/ui/data-number";
import type { LearningView, OutcomeView } from "@/lib/canonical-decision/types";

export function OutcomeLearning({
  outcome,
  learning,
}: {
  outcome: OutcomeView | null;
  learning: LearningView | null;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-2" data-testid="outcome-learning">
      <Card>
        <CardHeader>
          <CardTitle>Outcome</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {outcome ? (
            <>
              <div className="flex flex-wrap gap-2">
                <StatusBadge label={outcome.result ?? "unreviewed"} tone="info" />
                <DataNumber value={outcome.pnl ?? "—"} />
              </div>
              {outcome.lessons ? <p className="text-text-secondary">{outcome.lessons}</p> : null}
              <div className="flex flex-wrap gap-3">
                {outcome.href ? (
                  <Link href={outcome.href} className="text-accent underline">
                    Open outcome
                  </Link>
                ) : null}
                <Link href="/journal" className="text-accent underline">
                  Legacy journal
                </Link>
              </div>
            </>
          ) : (
            <p className="text-text-muted">No journaled outcome is linked yet.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Learning</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {learning ? (
            <>
              <StatusBadge label={learning.status ?? "open"} tone="pending" />
              <p>{learning.lessonText}</p>
              <p className="text-caption text-text-muted">{learning.mistakeType}</p>
              {learning.href ? (
                <Link href={learning.href} className="text-accent underline">
                  Review lesson
                </Link>
              ) : null}
            </>
          ) : (
            <p className="text-text-muted">
              No lesson candidate is linked. Lessons stay review-only and never auto-promote a
              strategy.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
