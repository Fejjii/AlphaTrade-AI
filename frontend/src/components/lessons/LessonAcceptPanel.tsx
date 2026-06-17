"use client";

import { useCallback, useEffect, useState } from "react";
import type { LessonCandidate, ProposedRuleUpdate, UserStrategy } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type AcceptPath = "accept_only" | "attach_rule" | "create_version";

type Props = {
  lesson: LessonCandidate;
  busy: boolean;
  onAccept: (payload: {
    path: AcceptPath;
    reviewerNotes: string;
    ruleUpdate: ProposedRuleUpdate | null;
    strategyId: string | null;
  }) => Promise<void>;
  onCancel: () => void;
};

export function LessonAcceptPanel({ lesson, busy, onAccept, onCancel }: Props) {
  const [path, setPath] = useState<AcceptPath>("accept_only");
  const [reviewerNotes, setReviewerNotes] = useState("");
  const [strategies, setStrategies] = useState<UserStrategy[]>([]);
  const [strategyId, setStrategyId] = useState<string>(lesson.related_strategy_id ?? "");
  const [ruleSummary, setRuleSummary] = useState(
    lesson.proposed_rule_update?.summary ?? "",
  );
  const [confirmed, setConfirmed] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadStrategies = useCallback(async () => {
    const { api } = await import("@/lib/api");
    const res = await api.strategies.list({ limit: 50 });
    setStrategies(res.items);
    if (!strategyId && res.items[0]) {
      setStrategyId(res.items[0].id);
    }
  }, [strategyId]);

  useEffect(() => {
    void loadStrategies();
  }, [loadStrategies]);

  const selectedStrategy = strategies.find((s) => s.id === strategyId);
  const needsStrategy = path !== "accept_only";
  const ruleUpdate: ProposedRuleUpdate | null =
    path === "accept_only"
      ? null
      : {
          summary: ruleSummary || "Lesson-driven rule update",
          structured_rules_patch: lesson.proposed_rule_update?.structured_rules_patch ?? null,
          attach_to_strategy: path === "attach_rule",
          create_new_version: path === "create_version",
        };

  async function handleConfirm() {
    if (!confirmed) {
      setError("Confirm you understand the active strategy will not be silently mutated.");
      return;
    }
    if (needsStrategy && !strategyId) {
      setError("Select a strategy for rule attachment or version creation.");
      return;
    }
    setError(null);
    try {
      await onAccept({
        path,
        reviewerNotes,
        ruleUpdate,
        strategyId: needsStrategy ? strategyId : lesson.related_strategy_id ?? null,
      });
      setSuccessMessage(
        path === "accept_only"
          ? "Lesson accepted — stored as reviewed trading memory."
          : path === "attach_rule"
            ? "Lesson accepted and rule update attached to current strategy version."
            : "Lesson accepted and new strategy version created.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Accept failed");
    }
  }

  if (successMessage) {
    return (
      <Card data-testid="lesson-accept-success">
        <CardContent className="space-y-2 p-4 text-sm text-emerald-300">
          <p>{successMessage}</p>
          <p className="text-zinc-400">Paper mode only — no live trading.</p>
          <Button variant="secondary" onClick={onCancel}>
            Close
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="lesson-accept-panel">
      <CardHeader>
        <CardTitle className="text-base">Accept lesson</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="rounded border border-amber-700/50 bg-amber-950/30 p-3 text-amber-100">
          Warning: the active strategy is never silently mutated. Choose an explicit path below.
        </p>

        <fieldset className="space-y-2">
          <legend className="text-zinc-400">Accept path</legend>
          {(
            [
              ["accept_only", "Accept lesson only"],
              ["attach_rule", "Accept and attach rule update to existing strategy"],
              ["create_version", "Accept and create new strategy version"],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className="flex items-start gap-2">
              <input
                type="radio"
                name={`accept-path-${lesson.id}`}
                checked={path === value}
                onChange={() => setPath(value)}
                data-testid={`accept-path-${value}`}
              />
              <span>{label}</span>
            </label>
          ))}
        </fieldset>

        {needsStrategy ? (
          <label className="block space-y-1">
            <span className="text-zinc-400">Strategy</span>
            <select
              className="w-full rounded border border-zinc-700 bg-zinc-900 p-2"
              value={strategyId}
              onChange={(e) => setStrategyId(e.target.value)}
              data-testid="lesson-strategy-select"
            >
              <option value="">Select strategy…</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} (v{s.current_version})
                </option>
              ))}
            </select>
            {selectedStrategy ? (
              <p className="text-xs text-zinc-500">
                Current version: v{selectedStrategy.current_version}
              </p>
            ) : null}
          </label>
        ) : null}

        {path !== "accept_only" ? (
          <label className="block space-y-1">
            <span className="text-zinc-400">Proposed rule update (editable)</span>
            <textarea
              className="w-full rounded border border-zinc-700 bg-zinc-900 p-2"
              rows={3}
              value={ruleSummary}
              onChange={(e) => setRuleSummary(e.target.value)}
              data-testid="rule-update-editor"
            />
            {lesson.proposed_rule_update?.structured_rules_patch ? (
              <p className="text-xs text-zinc-500">
                Structured rules patch will be applied when you confirm.
              </p>
            ) : null}
          </label>
        ) : lesson.proposed_rule_update ? (
          <p className="text-zinc-400">
            Proposed rule: {lesson.proposed_rule_update.summary}
          </p>
        ) : null}

        <label className="block space-y-1">
          <span className="text-zinc-400">Reviewer notes</span>
          <textarea
            className="w-full rounded border border-zinc-700 bg-zinc-900 p-2"
            rows={2}
            value={reviewerNotes}
            onChange={(e) => setReviewerNotes(e.target.value)}
            data-testid="accept-reviewer-notes"
          />
        </label>

        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            data-testid="accept-confirm-checkbox"
          />
          <span>I confirm this action — no silent strategy mutation.</span>
        </label>

        {error ? <p className="text-red-300">{error}</p> : null}

        <div className="flex gap-2">
          <Button disabled={busy} onClick={() => void handleConfirm()} data-testid="confirm-accept">
            {busy ? "Accepting…" : "Confirm accept"}
          </Button>
          <Button variant="secondary" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
