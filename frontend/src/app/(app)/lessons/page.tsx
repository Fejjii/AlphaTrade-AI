"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LessonAcceptPanel, type AcceptPath } from "@/components/lessons/LessonAcceptPanel";
import { LessonCandidateCard } from "@/components/lessons/LessonCandidateCard";
import { EmptyState, LoadingState } from "@/components/states";
import { api } from "@/lib/api";
import type { LessonCandidate, ProposedRuleUpdate } from "@/lib/api/types";

type Tab = "pending" | "accepted" | "rejected";
type SourceFilter = "all" | "coaching";

const TAB_DESCRIPTIONS: Record<Tab, string> = {
  pending:
    "Pending observations are not accepted trading rules — review them before they become memory.",
  accepted:
    "Accepted lessons are reviewed rules or memories. Accepting can optionally update a strategy version.",
  rejected: "Rejected lessons are archived as learning context only — they do not affect strategies.",
};

const EMPTY_STATES: Record<Tab, { title: string; description: string }> = {
  pending: {
    title: "No pending lessons",
    description: "New learning signals from journaling, analysis, and coaching will appear here for review.",
  },
  accepted: {
    title: "No accepted lessons yet",
    description: "Lessons you accept become reviewed rules or memories and show up here.",
  },
  rejected: {
    title: "No rejected lessons yet",
    description: "Lessons you archive as context only will be listed here.",
  },
};

const COACHING_EMPTY = {
  title: "No coaching lessons in this view",
  description: "Save a coaching prompt from the Coaching page to add a lesson candidate here.",
};

export default function LessonsPage() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>("pending");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [items, setItems] = useState<LessonCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [acceptingId, setAcceptingId] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("source") === "coaching") {
      setSourceFilter("coaching");
    }
  }, [searchParams]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === "accepted") {
        const res = await api.lessons.listAccepted();
        setItems(res.items);
      } else {
        const status = tab === "pending" ? "pending_review" : "rejected";
        const res = await api.lessons.listCandidates({ status });
        setItems(res.items);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load lessons");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredItems = useMemo(
    () =>
      sourceFilter === "coaching"
        ? items.filter((lesson) => lesson.source_type === "coaching")
        : items,
    [items, sourceFilter],
  );

  const coachingCount = useMemo(
    () => items.filter((lesson) => lesson.source_type === "coaching").length,
    [items],
  );

  const handleAcceptSubmit = async (
    id: string,
    payload: {
      path: AcceptPath;
      reviewerNotes: string;
      ruleUpdate: ProposedRuleUpdate | null;
      strategyId: string | null;
    },
  ) => {
    setBusyId(id);
    try {
      await api.lessons.accept(id, {
        reviewer_notes: payload.reviewerNotes,
        accepted_rule_update: payload.ruleUpdate ?? undefined,
        attach_rule_to_strategy: payload.path === "attach_rule",
        create_strategy_version: payload.path === "create_version",
        related_strategy_id: payload.strategyId ?? undefined,
      });
      setAcceptingId(null);
      await load();
    } catch (e) {
      throw e;
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (id: string) => {
    setBusyId(id);
    try {
      await api.lessons.reject(id, { reviewer_notes: notes[id] ?? "" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusyId(null);
    }
  };

  const emptyState =
    sourceFilter === "coaching" && items.length > 0 && filteredItems.length === 0
      ? COACHING_EMPTY
      : EMPTY_STATES[tab];

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 md:p-6" data-testid="lessons-page">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">Lessons</h1>
        <p className="text-sm text-zinc-400">
          Review discipline observations before they become accepted trading memory. Paper mode only.
        </p>
        <p className="mt-1 text-xs text-zinc-500" data-testid="lessons-tab-description">
          {TAB_DESCRIPTIONS[tab]}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2" role="tablist">
        {(["pending", "accepted", "rejected"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`rounded-lg px-3 py-1.5 text-sm capitalize ${
              tab === t ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:bg-zinc-900"
            }`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div
        className="flex flex-wrap items-center gap-2 text-xs"
        role="group"
        aria-label="Source filter"
        data-testid="lessons-source-filter"
      >
        <span className="text-zinc-500">Show:</span>
        <button
          type="button"
          data-testid="lessons-source-all"
          aria-pressed={sourceFilter === "all"}
          className={
            sourceFilter === "all"
              ? "rounded bg-zinc-100 px-3 py-1 font-medium text-zinc-900"
              : "rounded border border-zinc-700 px-3 py-1 text-zinc-300"
          }
          onClick={() => setSourceFilter("all")}
        >
          All sources
        </button>
        <button
          type="button"
          data-testid="lessons-source-coaching"
          aria-pressed={sourceFilter === "coaching"}
          className={
            sourceFilter === "coaching"
              ? "rounded bg-zinc-100 px-3 py-1 font-medium text-zinc-900"
              : "rounded border border-zinc-700 px-3 py-1 text-zinc-300"
          }
          onClick={() => setSourceFilter("coaching")}
        >
          From coaching{coachingCount ? ` (${coachingCount})` : ""}
        </button>
        {sourceFilter === "coaching" ? (
          <Link href="/coaching" className="text-zinc-400 underline">
            Back to coaching
          </Link>
        ) : null}
      </div>

      {error ? <p className="text-sm text-red-300">{error}</p> : null}
      {loading ? (
        <LoadingState label="Loading lessons…" />
      ) : filteredItems.length === 0 ? (
        <div data-testid={`lessons-empty-${tab}`}>
          <EmptyState title={emptyState.title} description={emptyState.description} />
        </div>
      ) : (
        <div className="space-y-4">
          {filteredItems.map((lesson) => (
            <div key={lesson.id} className="space-y-2">
              {acceptingId === lesson.id ? (
                <LessonAcceptPanel
                  lesson={lesson}
                  busy={busyId === lesson.id}
                  onAccept={(payload) => handleAcceptSubmit(lesson.id, payload)}
                  onCancel={() => setAcceptingId(null)}
                />
              ) : (
                <>
                  {tab === "pending" ? (
                    <label className="block text-xs text-zinc-500">
                      Reviewer notes (optional)
                      <textarea
                        className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 p-2 text-sm"
                        rows={2}
                        value={notes[lesson.id] ?? ""}
                        onChange={(e) =>
                          setNotes((prev) => ({ ...prev, [lesson.id]: e.target.value }))
                        }
                        data-testid={`reviewer-notes-${lesson.id}`}
                      />
                    </label>
                  ) : lesson.reviewer_notes ? (
                    <p className="text-xs text-zinc-500">Notes: {lesson.reviewer_notes}</p>
                  ) : null}
                  <LessonCandidateCard
                    lesson={lesson}
                    busy={busyId === lesson.id}
                    onAccept={tab === "pending" ? () => setAcceptingId(lesson.id) : undefined}
                    onReject={tab === "pending" ? () => handleReject(lesson.id) : undefined}
                  />
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
