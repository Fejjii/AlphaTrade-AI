"use client";

import { useCallback } from "react";

import { killSwitchBlockNotice, PortfolioHubChrome } from "@/components/portfolio";
import { PositionCard } from "@/components/PositionCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { describeSafetyPosture } from "@/components/workflows";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";

export default function PositionsPage() {
  const loader = useCallback(() => api.positions.list({ limit: 50 }), []);
  const { data, loading, error, reload } = useAsyncData(loader, []);
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const { killSwitchStatus, killSwitchError, loading: appLoading } = useAppContext();
  const posture = describeSafetyPosture(executionMode, realTradingEnabled);
  const block = killSwitchBlockNotice({
    killSwitchStatus,
    killSwitchError,
    killSwitchLoading: appLoading,
  });

  const closePaperPosition = useCallback(
    async (id: string, exitPrice: string) => {
      // The exit price is exactly what the user entered and confirmed — never a
      // fallback or the entry price. Failures propagate to the card, which keeps
      // the position visible and open; the list reloads only after success.
      await api.positions.closePaper(id, {
        exit_price: exitPrice,
        reason: "Paper close at user-entered exit price",
      });
      await reload();
    },
    [reload],
  );

  return (
    <PortfolioHubChrome
      title="Positions"
      description="Paper positions only. Close a simulated trade at an exit price you enter — no real exchange execution, no orders, and not investment advice."
      posture={posture}
      riskBlocked={block.blocked}
      riskBlockReason={block.reason}
      testId="positions-page"
    >
      {loading ? (
        <LoadingState label="Loading positions…" />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void reload()} />
      ) : data ? (
        <div className="grid gap-4">
          {data.items.length ? (
            data.items.map((position) => (
              <PositionCard
                key={position.id}
                position={position}
                onClosePaper={closePaperPosition}
              />
            ))
          ) : (
            <EmptyState
              title="No positions"
              description="Paper positions appear after approved execution."
            />
          )}
        </div>
      ) : null}
    </PortfolioHubChrome>
  );
}
