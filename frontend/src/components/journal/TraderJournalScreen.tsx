"use client";

import { useCallback } from "react";

import { TraderJournalView, type TraderJournalData } from "@/components/journal/TraderJournalView";
import { ErrorState, LoadingState } from "@/components/states";
import { loadSource } from "@/components/workflows";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export function TraderJournalScreen() {
  const loader = useCallback(async (): Promise<TraderJournalData> => {
    const [entries, trades, lessons, coaching] = await Promise.all([
      loadSource(api.journal.list({ limit: 30 })),
      loadSource(api.journal.listTrades({ limit: 20 })),
      loadSource(api.lessons.listCandidates()),
      loadSource(api.coaching.prompts()),
    ]);
    return { entries, trades, lessons, coaching };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);
  if (loading && !data) return <LoadingState label="Loading journal…" />;
  if (error || !data) {
    return <ErrorState message={error ?? "Journal unavailable"} onRetry={() => void reload()} />;
  }
  return <TraderJournalView data={data} />;
}
