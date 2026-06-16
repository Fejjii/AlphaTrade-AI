"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { StrategyCardForm } from "@/components/strategy/StrategyCardForm";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { StrategyCard, StrategyId } from "@/lib/api/types";

export default function EditStrategyPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params.id);
  const loader = useCallback(() => api.strategies.get(id), [id]);
  const { data, loading, error } = useAsyncData(loader, [id]);
  const [setupType, setSetupType] = useState<StrategyId>("htf_trend_pullback");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (data?.setup_type) {
      setSetupType(data.setup_type);
    }
  }, [data?.setup_type]);

  async function handleSubmit(card: StrategyCard) {
    setBusy(true);
    setSaveError(null);
    try {
      await api.strategies.update(id, {
        name: card.strategy_name,
        card: card as unknown as Record<string, unknown>,
      });
      router.push(`/strategy-lab/${id}`);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Update failed");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Edit strategy</h1>
        <p className="text-sm text-zinc-400">Creates a new version when the card changes.</p>
      </div>
      {loading ? <LoadingState label="Loading…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {saveError ? <ErrorState message={saveError} /> : null}
      {data?.latest_card ? (
        <StrategyCardForm
          initial={data.latest_card}
          setupType={setupType}
          onSetupTypeChange={(v) => setSetupType(v as StrategyId)}
          onSubmit={handleSubmit}
          submitLabel="Save new version"
          busy={busy}
        />
      ) : null}
    </div>
  );
}
