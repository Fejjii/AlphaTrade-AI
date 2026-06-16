"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState } from "react";

import { BacktestPanel } from "@/components/strategy/BacktestPanel";
import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";
import { emptyStrategyCard } from "@/components/strategy/StrategyCardForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { SETUP_TYPE_OPTIONS } from "@/lib/setup-types";

function setupLabel(value: string) {
  return SETUP_TYPE_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

export default function StrategyDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const loader = useCallback(() => api.strategies.get(id), [id]);
  const { data, loading, error, reload } = useAsyncData(loader, [id]);
  const [versionBusy, setVersionBusy] = useState(false);
  const [paperBusy, setPaperBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [paperSummary, setPaperSummary] = useState<Awaited<
    ReturnType<typeof api.strategies.paperValidation>
  > | null>(null);

  const card = data?.latest_card;

  async function createVersion() {
    if (!data) return;
    setVersionBusy(true);
    setActionError(null);
    try {
      const base = card ?? emptyStrategyCard(data.name);
      await api.strategies.createVersion(id, {
        card: { ...base, strategy_name: `${base.strategy_name} (rev)` },
        validation_status: "in_review",
      });
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Version failed");
    } finally {
      setVersionBusy(false);
    }
  }

  async function startPaperValidation() {
    setPaperBusy(true);
    setActionError(null);
    try {
      await api.strategies.startPaperValidation(id);
      const summary = await api.strategies.paperValidation(id);
      setPaperSummary(summary);
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Paper validation failed");
    } finally {
      setPaperBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{data?.name ?? "Strategy"}</h1>
          <p className="text-sm text-zinc-400">
            Setup: {data ? setupLabel(data.setup_type) : "—"} · v{data?.current_version ?? "—"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/strategy-lab/${id}/edit`}
            className="inline-flex h-10 items-center rounded-lg border border-zinc-700 px-4 text-sm hover:bg-zinc-900"
          >
            Edit card
          </Link>
          <Button variant="secondary" disabled={versionBusy} onClick={() => void createVersion()}>
            {versionBusy ? "Creating…" : "New version"}
          </Button>
        </div>
      </div>

      {loading ? <LoadingState label="Loading strategy…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {actionError ? <ErrorState message={actionError} /> : null}

      {data ? (
        <div className="flex flex-wrap gap-2 text-sm text-zinc-300">
          <span>Validation: {data.validation_status ?? "draft"}</span>
          <span>Backtest: {data.backtest_status ?? "not_run"}</span>
          <span>Paper: {data.paper_validation_status ?? "not_started"}</span>
          {data.paper_eligible ? <span className="text-emerald-400">Paper eligible</span> : null}
        </div>
      ) : null}

      {card ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[
            ["Entry", card.entry_conditions],
            ["Confirmation", card.confirmation_conditions],
            ["Invalidation", card.invalidation],
            ["Stop loss", card.stop_loss],
            ["Take profit", card.take_profit_plan],
            ["Runner", card.runner_plan],
            ["No trade rules", card.no_trade_rules],
          ].map(([title, items]) => (
            <Card key={title as string}>
              <CardHeader>
                <CardTitle className="text-base">{title as string}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-zinc-300">
                <ul className="list-disc space-y-1 pl-4">
                  {(items as string[]).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <BacktestPanel
          strategyId={id}
          onRun={(assumptions) => api.strategies.requestBacktest(id, { assumptions })}
          onLoadTrades={(runId) => api.strategies.listBacktestTrades(runId)}
        />
        <PaperValidationPanel
          summary={paperSummary}
          busy={paperBusy}
          onStart={() => void startPaperValidation()}
        />
      </div>
    </div>
  );
}
