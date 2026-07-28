"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { BacktestPanel } from "@/components/strategy/BacktestPanel";
import { PaperValidationPanel } from "@/components/strategy/PaperValidationPanel";
import { StrategyVersionHistory } from "@/components/strategy/StrategyVersionHistory";
import { StructuredRuleEditor } from "@/components/strategy/StructuredRuleEditor";
import { emptyStrategyCard } from "@/components/strategy/StrategyCardForm";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/states";
import { loadSource, type SourceResult } from "@/components/workflows";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { strategyStatusFor } from "@/lib/strategy-status";
import { buildWorkflowSteps } from "@/lib/workflow-steps";
import type {
  PaperAlert,
  PaperEligibilityReport,
  PaperRuntimeHistoryRecord,
  PaperSchedulerStatus,
  PaperSignalResult,
  PaperTradeRecord,
  PaperValidationSummary,
} from "@/lib/api/types";
import { SETUP_TYPE_OPTIONS } from "@/lib/setup-types";

function setupLabel(value: string) {
  return SETUP_TYPE_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

type PaperSources = {
  summary: SourceResult<PaperValidationSummary>;
  eligibility: SourceResult<PaperEligibilityReport>;
  scheduler: SourceResult<PaperSchedulerStatus>;
  alerts: SourceResult<{ items: PaperAlert[] }>;
  history: SourceResult<{ items: PaperRuntimeHistoryRecord[] }>;
  signals: SourceResult<{ items: PaperSignalResult[] }>;
  trades: SourceResult<{ items: PaperTradeRecord[] }>;
};

const idleSource = <T,>(): SourceResult<T> => ({
  data: null,
  available: false,
  error: null,
  fallbackUsed: false,
});

export default function StrategyDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const loader = useCallback(() => api.strategies.get(id), [id]);
  const { data, loading, error, reload } = useAsyncData(loader, [id]);
  const [versionBusy, setVersionBusy] = useState(false);
  const [paperBusy, setPaperBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [paperLoading, setPaperLoading] = useState(true);
  const [paperSources, setPaperSources] = useState<PaperSources>({
    summary: idleSource(),
    eligibility: idleSource(),
    scheduler: idleSource(),
    alerts: idleSource(),
    history: idleSource(),
    signals: idleSource(),
    trades: idleSource(),
  });
  const [rulesBusy, setRulesBusy] = useState(false);
  const paperLoadGeneration = useRef(0);

  const testabilityLoader = useCallback(() => api.strategies.testability(id), [id]);
  const { data: testabilityData, reload: reloadTestability } = useAsyncData(testabilityLoader, [id]);

  const versionsLoader = useCallback(() => api.strategies.listVersions(id), [id]);
  const { data: versionsData } = useAsyncData(versionsLoader, [id]);

  const loadPaperSources = useCallback(async () => {
    const generation = ++paperLoadGeneration.current;
    setPaperLoading(true);
    const [summary, eligibility, scheduler, alerts] = await Promise.all([
      loadSource(api.strategies.paperValidation(id)),
      loadSource(api.strategies.paperEligibility(id)),
      loadSource(api.strategies.schedulerStatus()),
      loadSource(api.alerts.list({ limit: 10 })),
    ]);
    if (generation !== paperLoadGeneration.current) return;

    const runId = summary.data?.runs[0]?.id;
    let signals: SourceResult<{ items: PaperSignalResult[] }> = {
      data: { items: [] },
      available: true,
      error: null,
      fallbackUsed: false,
    };
    let trades: SourceResult<{ items: PaperTradeRecord[] }> = {
      data: { items: [] },
      available: true,
      error: null,
      fallbackUsed: false,
    };
    let history: SourceResult<{ items: PaperRuntimeHistoryRecord[] }>;

    if (runId) {
      const [sig, tr, hist] = await Promise.all([
        loadSource(api.strategies.paperValidationSignals(runId)),
        loadSource(api.strategies.paperValidationTrades(runId)),
        loadSource(api.strategies.schedulerHistory({ run_id: runId, limit: 10 })),
      ]);
      signals = sig;
      trades = tr;
      history = hist;
    } else {
      history = await loadSource(api.strategies.schedulerHistory({ limit: 10 }));
      if (!summary.available) {
        signals = {
          data: null,
          available: false,
          error: "Paper signals unavailable until paper validation summary loads.",
          fallbackUsed: false,
        };
        trades = {
          data: null,
          available: false,
          error: "Paper trades unavailable until paper validation summary loads.",
          fallbackUsed: false,
        };
      }
    }

    if (generation !== paperLoadGeneration.current) return;
    setPaperSources({
      summary,
      eligibility,
      scheduler,
      alerts,
      history,
      signals,
      trades,
    });
    setPaperLoading(false);
  }, [id]);

  useEffect(() => {
    void loadPaperSources();
  }, [loadPaperSources, data?.current_version, data?.backtest_status]);

  const card = data?.latest_card;
  const latestRunId = paperSources.summary.data?.runs[0]?.id;
  const eligibility = paperSources.eligibility.data;
  const paperSummary = paperSources.summary.data;
  const scheduler = paperSources.scheduler.data;
  const history = paperSources.history.data?.items ?? [];
  const alerts = paperSources.alerts.data?.items ?? [];
  const signals = paperSources.signals.data?.items ?? [];
  const trades = paperSources.trades.data?.items ?? [];

  const paperSourceStatuses = [
    {
      name: "Paper validation summary",
      available: paperSources.summary.available,
      error: paperSources.summary.error,
      empty: paperSources.summary.available && (paperSources.summary.data?.runs.length ?? 0) === 0,
    },
    {
      name: "Paper eligibility",
      available: paperSources.eligibility.available,
      error: paperSources.eligibility.error,
      empty: false,
    },
    {
      name: "Scheduler status",
      available: paperSources.scheduler.available,
      error: paperSources.scheduler.error,
      empty: false,
    },
    {
      name: "Paper alerts",
      available: paperSources.alerts.available,
      error: paperSources.alerts.error,
      empty: paperSources.alerts.available && (paperSources.alerts.data?.items.length ?? 0) === 0,
    },
    {
      name: "Runtime history",
      available: paperSources.history.available,
      error: paperSources.history.error,
      empty: paperSources.history.available && history.length === 0,
    },
    {
      name: "Paper signals",
      available: paperSources.signals.available,
      error: paperSources.signals.error,
      empty: paperSources.signals.available && signals.length === 0,
    },
    {
      name: "Paper trades",
      available: paperSources.trades.available,
      error: paperSources.trades.error,
      empty: paperSources.trades.available && trades.length === 0,
    },
  ];

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
      await loadPaperSources();
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Paper validation failed");
    } finally {
      setPaperBusy(false);
    }
  }

  return (
    <div className="space-y-6" data-testid="strategy-detail-page">
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
        <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-300">
          <Badge variant={strategyStatusFor(data).variant} data-testid="strategy-status-badge">
            {strategyStatusFor(data).label}
          </Badge>
          <span>Backtest: {data.backtest_status ?? "not_run"}</span>
          <span>Paper: {data.paper_validation_status ?? "not_started"}</span>
          {eligibility ? (
            <span data-testid="strategy-paper-status">Eligibility: {eligibility.status}</span>
          ) : null}
        </div>
      ) : null}

      {data ? (
        <WorkflowStepper
          steps={buildWorkflowSteps({
            strategyId: id,
            hasStructuredRules: testabilityData?.has_structured_rules,
            readyForBacktest: testabilityData?.ready_for_backtest,
            backtestStatus: data.backtest_status,
            paperValidationStatus: data.paper_validation_status,
            paperEligible: eligibility?.paper_eligible ?? data.paper_eligible,
            unresolvedLessonCount: eligibility?.unresolved_lesson_candidates.length,
          })}
        />
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

      <section
        aria-labelledby="strategy-paper-sources-heading"
        className="space-y-2"
        data-testid="strategy-paper-sources"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2
            id="strategy-paper-sources-heading"
            className="text-lg font-semibold text-text-primary"
          >
            Paper validation sources
          </h2>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={paperLoading || paperBusy}
            onClick={() => void loadPaperSources()}
            data-testid="strategy-paper-sources-retry"
          >
            Retry paper sources
          </Button>
        </div>
        {paperLoading ? (
          <LoadingState label="Loading paper validation sources…" />
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2" data-testid="strategy-paper-source-list">
            {paperSourceStatuses.map((source) => (
              <li
                key={source.name}
                data-testid={`strategy-paper-source-${source.name.toLowerCase().replace(/\s+/g, "-")}`}
                className="rounded-control border border-border-subtle px-3 py-2 text-sm"
              >
                <p className="font-medium text-text-primary">{source.name}</p>
                {!source.available ? (
                  <p className="mt-1 text-danger" role="alert">
                    Unavailable{source.error ? `: ${source.error}` : "."}
                  </p>
                ) : source.empty ? (
                  <p className="mt-1 text-text-muted">Loaded — empty.</p>
                ) : (
                  <p className="mt-1 text-text-secondary">Loaded.</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <BacktestPanel
          strategyId={id}
          onRun={(body) => api.strategies.requestBacktest(id, body)}
          onLoadTrades={(runId) => api.strategies.listBacktestTrades(runId)}
          onListRuns={() => api.strategies.listBacktests(id)}
        />
        <PaperValidationPanel
          summary={paperSummary}
          eligibility={eligibility}
          scheduler={scheduler}
          history={paperSources.history.available ? history : []}
          alerts={paperSources.alerts.available ? alerts : []}
          busy={paperBusy || paperLoading}
          signals={paperSources.signals.available ? signals : []}
          trades={paperSources.trades.available ? trades : []}
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
