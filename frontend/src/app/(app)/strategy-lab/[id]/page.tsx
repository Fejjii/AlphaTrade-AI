"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { BacktestPanel } from "@/components/strategy/BacktestPanel";
import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";
import { StrategyVersionHistory } from "@/components/strategy/StrategyVersionHistory";
import { StructuredRuleEditor } from "@/components/strategy/StructuredRuleEditor";
import { emptyStrategyCard } from "@/components/strategy/StrategyCardForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type {
  PaperAlert,
  PaperEligibilityReport,
  PaperRuntimeHistoryRecord,
  PaperSchedulerStatus,
  PaperSignalResult,
  PaperTradeRecord,
} from "@/lib/api/types";
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
  const [eligibility, setEligibility] = useState<PaperEligibilityReport | null>(null);
  const [signals, setSignals] = useState<PaperSignalResult[]>([]);
  const [trades, setTrades] = useState<PaperTradeRecord[]>([]);
  const [scheduler, setScheduler] = useState<PaperSchedulerStatus | null>(null);
  const [history, setHistory] = useState<PaperRuntimeHistoryRecord[]>([]);
  const [alerts, setAlerts] = useState<PaperAlert[]>([]);
  const [rulesBusy, setRulesBusy] = useState(false);

  const testabilityLoader = useCallback(() => api.strategies.testability(id), [id]);
  const { data: testabilityData, reload: reloadTestability } = useAsyncData(testabilityLoader, [id]);

  const versionsLoader = useCallback(() => api.strategies.listVersions(id), [id]);
  const { data: versionsData } = useAsyncData(versionsLoader, [id]);

  const latestRunId = paperSummary?.runs[0]?.id;

  async function refreshPaperData() {
    const [summary, report, sched, alertList] = await Promise.all([
      api.strategies.paperValidation(id),
      api.strategies.paperEligibility(id),
      api.strategies.schedulerStatus(),
      api.alerts.list({ limit: 10 }),
    ]);
    setPaperSummary(summary);
    setEligibility(report);
    setScheduler(sched);
    setAlerts(alertList.items);
    const runId = summary.runs[0]?.id;
    if (runId) {
      const [sig, tr, hist] = await Promise.all([
        api.strategies.paperValidationSignals(runId),
        api.strategies.paperValidationTrades(runId),
        api.strategies.schedulerHistory({ run_id: runId, limit: 10 }),
      ]);
      setSignals(sig.items);
      setTrades(tr.items);
      setHistory(hist.items);
    } else {
      const hist = await api.strategies.schedulerHistory({ limit: 10 });
      setHistory(hist.items);
    }
  }

  useEffect(() => {
    void api.strategies.paperEligibility(id).then(setEligibility).catch(() => setEligibility(null));
    void api.strategies.paperValidation(id).then(setPaperSummary).catch(() => setPaperSummary(null));
  }, [id, data?.current_version, data?.backtest_status]);

  useEffect(() => {
    if (!latestRunId) return;
    void Promise.all([
      api.strategies.paperValidationSignals(latestRunId),
      api.strategies.paperValidationTrades(latestRunId),
    ])
      .then(([sig, tr]) => {
        setSignals(sig.items);
        setTrades(tr.items);
      })
      .catch(() => {
        setSignals([]);
        setTrades([]);
      });
  }, [latestRunId]);

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

  async function withPaperAction(action: () => Promise<void>) {
    setPaperBusy(true);
    setActionError(null);
    try {
      await action();
      await refreshPaperData();
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
          {eligibility ? (
            <span data-testid="strategy-paper-status">
              Eligibility: {eligibility.status}
            </span>
          ) : null}
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

      <StructuredRuleEditor
        rules={testabilityData?.structured_rules ?? null}
        testability={testabilityData ?? null}
        busy={rulesBusy}
        onSave={async (rules) => {
          setRulesBusy(true);
          setActionError(null);
          try {
            await api.strategies.patchStructuredRules(id, rules);
            await reloadTestability();
          } catch (err) {
            setActionError(err instanceof Error ? err.message : "Save failed");
          } finally {
            setRulesBusy(false);
          }
        }}
      />

      {versionsData ? <StrategyVersionHistory versions={versionsData.items} /> : null}

      <div className="grid gap-4 md:grid-cols-2">
        <BacktestPanel
          strategyId={id}
          onRun={(assumptions) => api.strategies.requestBacktest(id, { assumptions })}
          onLoadTrades={(runId) => api.strategies.listBacktestTrades(runId)}
        />
        <PaperValidationPanel
          summary={paperSummary}
          eligibility={eligibility}
          scheduler={scheduler}
          history={history}
          alerts={alerts}
          busy={paperBusy}
          signals={signals}
          trades={trades}
          onStart={() =>
            void withPaperAction(async () => {
              await api.strategies.startPaperValidation(id, { runtime_mode: "scan_only" });
            })
          }
          onScan={() =>
            void withPaperAction(async () => {
              if (!latestRunId) throw new Error("Start paper validation first.");
              await api.strategies.scanPaperValidation(latestRunId);
            })
          }
          onTick={() =>
            void withPaperAction(async () => {
              if (!latestRunId) throw new Error("Start paper validation first.");
              await api.strategies.tickPaperValidation(latestRunId);
            })
          }
          onStop={() =>
            void withPaperAction(async () => {
              if (!latestRunId) throw new Error("Start paper validation first.");
              await api.strategies.stopPaperValidation(latestRunId);
            })
          }
          onSchedulerTick={() =>
            void withPaperAction(async () => {
              await api.strategies.schedulerTick();
            })
          }
          onMarkAlertRead={(alertId) =>
            void withPaperAction(async () => {
              await api.alerts.markRead(alertId);
            })
          }
        />
      </div>
    </div>
  );
}
