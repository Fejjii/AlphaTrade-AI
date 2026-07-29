"use client";

import Link from "next/link";

import { DataNumber } from "@/components/ui/data-number";
import type { SourceResult } from "@/components/workflows";
import type { DisciplineAnalyticsResponse, DisciplineScoreResult } from "@/lib/api/types";

import { ChartFrame } from "./ChartFrame";
import { SOURCE_DISCIPLINE_SCORE, SOURCE_LEARNING_DISCIPLINE } from "./sourceLabels";

type DisciplineScoreCardsProps = {
  proposalSource: SourceResult<DisciplineScoreResult> | null;
  learningSource: SourceResult<DisciplineAnalyticsResponse> | null;
  proposalLoading?: boolean;
  learningLoading?: boolean;
  onRetryProposal?: () => void;
  onRetryLearning?: () => void;
  proposalFiltersSummary?: string;
  learningFiltersSummary?: string;
  proposalFreshnessNote?: string;
  learningFreshnessNote?: string;
  staleWholeTab?: boolean;
};

function scoreLabel(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(0);
}

export function DisciplineScoreCards({
  proposalSource,
  learningSource,
  proposalLoading = false,
  learningLoading = false,
  onRetryProposal,
  onRetryLearning,
  proposalFiltersSummary,
  learningFiltersSummary,
  proposalFreshnessNote,
  learningFreshnessNote,
  staleWholeTab = false,
}: DisciplineScoreCardsProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="discipline-score-cards">
      <ChartFrame
        title="Proposal-flow discipline score"
        sourceLabel={SOURCE_DISCIPLINE_SCORE}
        filtersSummary={proposalFiltersSummary}
        derivedNote={proposalFreshnessNote}
        loading={proposalLoading && !proposalSource}
        error={
          proposalSource && !proposalSource.available
            ? proposalSource.error ?? "Proposal-flow discipline unavailable"
            : null
        }
        onRetry={onRetryProposal}
        empty={false}
        staleWholeTab={staleWholeTab}
        data-testid="discipline-proposal-card"
      >
        {proposalSource?.available && proposalSource.data ? (
          <div className="space-y-3">
            <p className="text-caption text-text-muted" data-testid="discipline-proposal-source-label">
              Source: proposal-flow / legacy journal analytics — not the validation-session score.
            </p>
            <div className="flex flex-wrap items-end gap-6">
              <div>
                <p className="text-caption text-text-muted">Score</p>
                <DataNumber
                  value={scoreLabel(proposalSource.data.score)}
                  className="text-2xl"
                  data-testid="discipline-proposal-score"
                />
              </div>
              <div>
                <p className="text-caption text-text-muted">Grade</p>
                <p className="text-lg text-text-primary" data-testid="discipline-proposal-grade">
                  {proposalSource.data.grade || "—"}
                </p>
              </div>
            </div>
            <p className="text-sm text-text-secondary">
              Canonical detail:{" "}
              <Link href="/" className="underline" data-testid="discipline-proposal-source-link">
                Dashboard discipline snapshot
              </Link>
            </p>
          </div>
        ) : null}
      </ChartFrame>

      <ChartFrame
        title="Validation-session discipline score"
        sourceLabel={SOURCE_LEARNING_DISCIPLINE}
        filtersSummary={learningFiltersSummary}
        derivedNote={learningFreshnessNote}
        sampleSize={learningSource?.available ? learningSource.data?.sample_size ?? null : null}
        sampleLabel="validation sessions"
        loading={learningLoading && !learningSource}
        error={
          learningSource && !learningSource.available
            ? learningSource.error ?? "Validation-session discipline unavailable"
            : null
        }
        onRetry={onRetryLearning}
        empty={false}
        insufficientSample={
          learningSource?.available && learningSource.data?.insufficient_data
            ? { n: learningSource.data.sample_size }
            : null
        }
        staleWholeTab={staleWholeTab}
        data-testid="discipline-learning-card"
      >
        {learningSource?.available && learningSource.data ? (
          <div className="space-y-3">
            <p className="text-caption text-text-muted" data-testid="discipline-learning-source-label">
              Source: paper-validation session assessments — not the proposal-flow score. Scores are
              never averaged or substituted.
            </p>
            <div className="flex flex-wrap items-end gap-6">
              <div>
                <p className="text-caption text-text-muted">Score</p>
                <DataNumber
                  value={
                    learningSource.data.insufficient_data
                      ? "—"
                      : scoreLabel(learningSource.data.discipline_score)
                  }
                  className="text-2xl"
                  data-testid="discipline-learning-score"
                />
              </div>
              <div>
                <p className="text-caption text-text-muted">Grade</p>
                <p className="text-lg text-text-primary" data-testid="discipline-learning-grade">
                  {learningSource.data.discipline_grade || "—"}
                </p>
              </div>
            </div>
            <p className="text-sm text-text-secondary">
              Canonical detail:{" "}
              <Link
                href="/learning-analytics"
                className="underline"
                data-testid="discipline-learning-source-link"
              >
                Learning Analytics
              </Link>
            </p>
          </div>
        ) : null}
      </ChartFrame>
    </div>
  );
}
