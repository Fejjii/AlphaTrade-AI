"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { CoachingPrompt, CoachingSaveRequest } from "@/lib/api/types";

const SEVERITY_VARIANT: Record<string, "default" | "warning" | "danger" | "muted"> = {
  low: "muted",
  medium: "warning",
  high: "default",
  critical: "danger",
};

export function CoachingPromptCard({
  prompt,
  minSample,
  startDate,
  endDate,
  onSaved,
}: {
  prompt: CoachingPrompt;
  minSample: number;
  startDate?: string;
  endDate?: string;
  onSaved?: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(prompt.already_saved_lesson_id ?? null);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const body: CoachingSaveRequest = {
        category: prompt.category,
        matched_dimension: prompt.source.matched_dimension,
        matched_key: prompt.source.matched_key,
        min_sample: minSample,
        ...(startDate ? { start_date: startDate } : {}),
        ...(endDate ? { end_date: endDate } : {}),
      };
      const result = await api.coaching.savePrompt(body);
      setSavedId(result.id);
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save coaching prompt.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card data-testid={`coaching-prompt-${prompt.signature}`}>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-base">{prompt.title}</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Badge variant={SEVERITY_VARIANT[prompt.severity] ?? "default"}>{prompt.severity}</Badge>
            <Badge variant="muted">{prompt.category.replaceAll("_", " ")}</Badge>
          </div>
        </div>
        <p className="text-xs text-zinc-500">
          concern {prompt.concern_score} · reliability {prompt.reliability} · n=
          {prompt.source.sample_size}
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-zinc-300">
        <p data-testid="coaching-prompt-text">{prompt.prompt_text}</p>

        {prompt.rationale.length ? (
          <ul className="list-disc space-y-1 pl-4 text-xs text-zinc-500" data-testid="coaching-rationale">
            {prompt.rationale.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}

        <div className="text-xs text-zinc-500" data-testid="coaching-source">
          <p>
            Source: {prompt.source.matched_dimension} / {prompt.source.matched_key}
          </p>
          {prompt.source.analytics_codes.length ? (
            <p>Analytics: {prompt.source.analytics_codes.join(", ")}</p>
          ) : null}
          {prompt.source.source_session_ids.length ? (
            <p>Sessions cited: {prompt.source.source_session_ids.length}</p>
          ) : null}
        </div>

        {savedId ? (
          <div
            className="space-y-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs"
            data-testid="coaching-save-success"
          >
            <p className="text-emerald-300">Saved to your lesson review queue.</p>
            <Link
              href="/lessons?source=coaching"
              className="inline-block font-medium text-emerald-200 underline"
              data-testid="coaching-in-review-queue"
            >
              Review in Lessons →
            </Link>
          </div>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={saving}
            onClick={() => void handleSave()}
            data-testid="coaching-save-button"
          >
            {saving ? "Saving…" : "Save to review queue"}
          </Button>
        )}

        {error ? <p className="text-xs text-red-400">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
