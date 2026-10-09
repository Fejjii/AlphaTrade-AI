"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useSearchParams } from "next/navigation";

import { JournalHubScreen } from "@/components/journal/JournalHubScreen";
import { parseJournalQuery } from "@/components/journal/journalContext";
import { JournalTradeScreen } from "@/components/journal/JournalTradeScreen";
import { TraderJournalScreen } from "@/components/journal/TraderJournalScreen";

export default function JournalPage() {
  const { user, organization } = useAuth();
  const searchParams = useSearchParams();
  const context = parseJournalQuery(searchParams);
  if (context.tradeId) return <JournalTradeScreen key={`${organization?.id}:${user?.id}:${context.tradeId}`} tradeId={context.tradeId} />;
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
