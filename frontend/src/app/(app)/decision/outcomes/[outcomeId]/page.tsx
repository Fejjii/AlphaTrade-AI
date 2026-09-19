"use client";

import { useCallback, useMemo } from "react";
import { useParams } from "next/navigation";

import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { OutcomeLearning } from "@/components/canonical-decision/OutcomeLearning";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { loadSource } from "@/components/workflows";
import {
  learningFromCanonicalRecord,
  outcomeFromCanonicalRecord,
} from "@/lib/canonical-decision/compose";

export default function DecisionOutcomePage() {
  const params = useParams<{ outcomeId: string }>();
  const outcomeId = params.outcomeId;

  const loader = useCallback(async () => {
    const [entry, lessons, learning] = await Promise.all([
      loadSource(api.journal.get(outcomeId)),
      loadSource(api.lessons.listCandidates()),
      loadSource(api.canonical.getLearningRecord(outcomeId)),
    ]);
    if (!entry.data && !learning.data) {
      throw new Error(entry.error ?? learning.error ?? "Outcome not found");
    }
    return { entry: entry.data, lessons: lessons.data, learning: learning.data };
  }, [outcomeId]);

  const { data, loading, error, reload } = useAsyncData(loader, [outcomeId]);
  const lesson = useMemo(
    () => data?.lessons?.items.find((item) => item.related_journal_entry_id === outcomeId),
    [data, outcomeId],
  );

  return (
    <DecisionChrome
      title="Outcome"
      description="Journaled paper result and canonical learning records. Lessons stay review-only."
      current="outcome"
    >
      {loading ? <LoadingState label="Loading outcome…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {data ? (
        <OutcomeLearning
          outcome={
            data.learning
              ? outcomeFromCanonicalRecord(data.learning)
              : data.entry
                ? {
                    journalId: data.entry.id,
                    positionId: data.entry.linked_position_id ?? null,
                    proposalId: data.entry.linked_proposal_id ?? null,
                    symbol: data.entry.symbol,
                    result: data.entry.result,
                    pnl: data.entry.pnl ?? null,
                    lessons: data.entry.lessons ?? null,
                    href: `/journal?entry=${data.entry.id}`,
                  }
                : null
          }
          learning={
            data.learning
              ? learningFromCanonicalRecord(data.learning)
              : lesson
                ? {
                    lessonId: lesson.id,
                    status: lesson.status,
                    lessonText: lesson.lesson_text,
                    mistakeType: lesson.mistake_type,
                    href: `/lessons?id=${lesson.id}`,
                  }
                : null
          }
        />
      ) : null}
    </DecisionChrome>
  );
}
