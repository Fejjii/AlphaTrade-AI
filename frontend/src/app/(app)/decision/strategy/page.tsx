"use client";

import { useCallback } from "react";

import { DecisionChrome } from "@/components/canonical-decision/DecisionChrome";
import { StrategyPerformance } from "@/components/canonical-decision/StrategyPerformance";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { loadSource } from "@/components/workflows";

export default function DecisionStrategyPage() {
  const loader = useCallback(async () => {
    const [quality, learning, setups] = await Promise.all([
      loadSource(api.strategyQuality.summary()),
      loadSource(api.learningAnalytics.summary()),
      loadSource(api.analytics.setups()),
    ]);
    return { quality, learning, setups };
  }, []);
  const { data, loading, error, reload } = useAsyncData(loader, []);

  return (
    <DecisionChrome
      title="Strategy and pattern performance"
      description="Existing strategy-quality, learning-analytics, and setup APIs. No automatic rule promotion."
      current="learning"
    >
      {loading ? <LoadingState label="Loading strategy performance…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {data ? (
        <StrategyPerformance
          quality={data.quality.data}
          learning={data.learning.data}
          setups={data.setups.data}
        />
      ) : null}
    </DecisionChrome>
  );
}
