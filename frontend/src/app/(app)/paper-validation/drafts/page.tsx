"use client";

import { useCallback, useMemo } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import {
  DraftSummaryCard,
  ValidatePageChrome,
} from "@/components/validate";
import { describeSafetyPosture, loadSource, type SourceResult } from "@/components/workflows";
import { useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

type DraftsPageData = {
  drafts: SourceResult<Awaited<ReturnType<typeof api.strategies.drafts>>>;
};

export default function PaperValidationDraftsPage() {
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);

  const loader = useCallback(async (): Promise<DraftsPageData> => {
    return { drafts: await loadSource(api.strategies.drafts({ limit: 50 })) };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);
  const drafts = data?.drafts;
  const available = drafts?.available ?? false;
  const items = available ? (drafts?.data?.items ?? []) : [];
  const total = available ? (drafts?.data?.total ?? 0) : null;

  const freshnessSources = useMemo(
    () => [
      {
        name: "Drafts",
        available,
        required: true,
        timestamp: items[0]?.created_at ?? null,
      },
    ],
    [available, items],
  );

  if (loading && !data) return <LoadingState label="Loading paper drafts…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void reload()} />;

  return (
    <ValidatePageChrome
      title="Paper Validation Drafts"
      description="Non-executable paper-trade ideas from reviewed setup alerts. Drafts never place orders, send Telegram messages, or trigger execution."
      posture={posture}
      providerMode={providerMode}
      freshnessSources={freshnessSources}
      testId="paper-validation-drafts-page"
      activeHref="/paper-validation/drafts"
    >
      {!available ? (
        <ErrorState
          message={drafts?.error ?? "Draft source unavailable. Count is not shown as zero."}
          onRetry={() => void reload()}
        />
      ) : (
        <>
          <p className="text-sm text-text-secondary" data-testid="paper-drafts-total">
            Active drafts:{" "}
            <span className="font-semibold text-text-primary">
              {total == null ? "unavailable" : total}
            </span>
          </p>

          {items.length ? (
            <div className="space-y-3" data-testid="paper-validation-drafts-list">
              {items.map((draft) => (
                <DraftSummaryCard key={draft.draft_id} draft={draft} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No paper drafts yet"
              description="Mark a setup alert as watching or important, then create a paper draft from the review page. Available draft source returned an empty list."
            />
          )}
        </>
      )}
    </ValidatePageChrome>
  );
}
