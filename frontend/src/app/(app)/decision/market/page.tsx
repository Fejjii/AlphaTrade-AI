"use client";

import { useCallback, useMemo, useState } from "react";

import { ActionEligibilityCard } from "@/components/canonical-decision/ActionEligibilityCard";
import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { MarketQualityCard } from "@/components/canonical-decision/MarketQualityCard";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { api } from "@/lib/api";
import type { MarketAnalyzeResponse } from "@/lib/api/types";
import { projectActionEligibility } from "@/lib/canonical-decision/eligibility";
import { marketQualityFromAnalysis } from "@/lib/canonical-decision/compose";

export default function DecisionMarketPage() {
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<MarketAnalyzeResponse | null>(null);

  const quality = useMemo(
    () => (analysis ? marketQualityFromAnalysis(analysis, symbol, timeframe) : null),
    [analysis, symbol, timeframe],
  );
  const eligibility = useMemo(
    () =>
      projectActionEligibility({
        killSwitchActive,
        executionMode,
        realTradingEnabled,
        setupConfirmed: quality?.grade === "tradeable",
      }),
    [killSwitchActive, executionMode, realTradingEnabled, quality],
  );

  const analyze = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.market.analyze({ symbol, timeframe });
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Market analysis failed");
    } finally {
      setBusy(false);
    }
  }, [symbol, timeframe]);

  return (
    <DecisionChrome
      title="Market assessment"
      description="Inspect market quality and evidence freshness. A tradeable setup is not permission to act."
      current="market_assessment"
      eligibilityBlocked={eligibility.state !== "eligible"}
    >
      <form
        className="grid gap-3 sm:grid-cols-[1fr_8rem_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          void analyze();
        }}
      >
        <div>
          <Label htmlFor="decision-symbol">Symbol</Label>
          <Input
            id="decision-symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.toUpperCase())}
          />
        </div>
        <div>
          <Label htmlFor="decision-timeframe">Timeframe</Label>
          <Input
            id="decision-timeframe"
            value={timeframe}
            onChange={(event) => setTimeframe(event.target.value)}
          />
        </div>
        <div className="flex items-end">
          <Button type="submit" className="min-h-11 w-full" disabled={busy}>
            {busy ? "Assessing…" : "Assess market"}
          </Button>
        </div>
      </form>
      {error ? <ErrorState message={error} /> : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {quality ? <MarketQualityCard quality={quality} /> : null}
        <ActionEligibilityCard eligibility={eligibility} />
      </div>
    </DecisionChrome>
  );
}
