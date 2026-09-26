"use client";

import { useSearchParams } from "next/navigation";

import { JournalHubScreen } from "@/components/journal/JournalHubScreen";
import { parseJournalQuery } from "@/components/journal/journalContext";
import { TraderJournalScreen } from "@/components/journal/TraderJournalScreen";

export default function JournalPage() {
  const searchParams = useSearchParams();
  const context = parseJournalQuery(searchParams);
  const record =
    searchParams.get("view") === "record" ||
    Boolean(
      context.proposalId ||
        context.positionId ||
        context.entryId ||
        context.tradeId ||
        context.sessionId,
    );
  if (record) return <JournalHubScreen />;
  return <TraderJournalScreen />;
}
