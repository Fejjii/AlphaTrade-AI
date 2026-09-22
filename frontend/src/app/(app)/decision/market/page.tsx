"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ActionEligibilityCard } from "@/components/canonical-decision/ActionEligibilityCard";
import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { MarketQualityCard } from "@/components/canonical-decision/MarketQualityCard";
import { PerpetualMarketStatusCard } from "@/components/canonical-decision/PerpetualMarketStatusCard";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { api } from "@/lib/api";
import type { CanonicalEvidenceRead, CanonicalMarketMonitorStatusRead } from "@/lib/api/types";
import { projectActionEligibility } from "@/lib/canonical-decision/eligibility";
import {
  marketQualityFromCanonicalEvidence,
  perpetualMarketStatusFromCanonical,
} from "@/lib/canonical-decision/compose";

export default function DecisionMarketPage() {
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<CanonicalEvidenceRead | null>(null);
  const [monitor, setMonitor] = useState<CanonicalMarketMonitorStatusRead | null>(null);

  const quality = useMemo(
    () => (evidence ? marketQualityFromCanonicalEvidence(evidence) : null),
    [evidence],
  );
  const marketStatus = useMemo(
    () => (monitor ? perpetualMarketStatusFromCanonical(monitor) : null),
    [monitor],
  );
  const eligibility = useMemo(
    () =>
      projectActionEligibility({
        killSwitchActive,
        executionMode,
        realTradingEnabled,
        setupConfirmed: false,
      }),
    [killSwitchActive, executionMode, realTradingEnabled],
  );

  const loadEvidence = useCallback(async (nextSymbol: string) => {
    setBusy(true);
    setError(null);
    try {
      const [result, status] = await Promise.all([
        api.canonical.getEvidence({ symbol: nextSymbol }),
        api.canonical.getMarketStatus({ symbol: nextSymbol }),
      ]);
      setEvidence(result);
      setMonitor(status);
    } catch (err) {
      setEvidence(null);
      setMonitor(null);
      setError(err instanceof Error ? err.message : "Canonical evidence read failed");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadEvidence("BTCUSDT");
  }, [loadEvidence]);

  return (
    <DecisionChrome
      title="Market assessment"
      description="Canonical USD-M evidence and freshness. Replay fixtures and stale data are never live marks. A complete window is not permission to act."
      current="market_assessment"
      eligibilityBlocked={eligibility.state !== "eligible"}
    >
      <form
        className="grid gap-3 sm:grid-cols-[1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          void loadEvidence(symbol);
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
        <div className="flex items-end">
          <Button type="submit" className="min-h-11 w-full" disabled={busy}>
            {busy ? "Reading…" : "Read canonical evidence"}
          </Button>
        </div>
      </form>
      <p className="text-caption text-text-muted" data-testid="canonical-first-slice-copy">
        First slice: Binance USD-M perpetual · trigger 15m · context 4h. Watcher is not activated.
        Default source is replay.
      </p>
      {error ? <ErrorState message={error} /> : null}
      {marketStatus ? <PerpetualMarketStatusCard status={marketStatus} /> : null}
      <div className="grid gap-4 xl:grid-cols-2" data-testid="canonical-evidence-read">
        {quality ? <MarketQualityCard quality={quality} /> : null}
        <ActionEligibilityCard eligibility={eligibility} />
      </div>
    </DecisionChrome>
  );
}
