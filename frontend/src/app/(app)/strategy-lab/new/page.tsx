"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { emptyStrategyCard, StrategyCardForm } from "@/components/strategy/StrategyCardForm";
import { ErrorState } from "@/components/states";
import { api } from "@/lib/api";
import type { StrategyId } from "@/lib/api/types";

export default function NewStrategyPage() {
  const router = useRouter();
  const [setupType, setSetupType] = useState<StrategyId>("htf_trend_pullback");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(card: ReturnType<typeof emptyStrategyCard>) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.strategies.create({
        name: card.strategy_name,
        setup_type: setupType,
        card: card as unknown as Record<string, unknown>,
      });
      router.push(`/strategy-lab/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Create strategy</h1>
        <p className="text-sm text-zinc-400">Paper-only strategy card (deterministic rules).</p>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <StrategyCardForm
        initial={emptyStrategyCard()}
        setupType={setupType}
        onSetupTypeChange={(v) => setSetupType(v as StrategyId)}
        onSubmit={handleSubmit}
        submitLabel="Create strategy"
        busy={busy}
      />
    </div>
  );
}
