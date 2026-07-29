"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { loadSource, type SourceResult } from "@/components/workflows";
import { api } from "@/lib/api";
import type {
  PaperAlert,
  PaperEligibilityReport,
  PaperRuntimeHistoryRecord,
  PaperSchedulerStatus,
  PaperSignalResult,
  PaperTradeRecord,
  PaperValidationSummary,
} from "@/lib/api/types";

export type PaperSourceKey =
  | "summary"
  | "eligibility"
  | "scheduler"
  | "alerts"
  | "history"
  | "signals"
  | "trades";

export type PaperSourceStatus =
  | "idle"
  | "loading"
  | "waiting"
  | "ready"
  | "empty"
  | "failed";

export type PaperSourceSlot<T> = {
  status: PaperSourceStatus;
  data: T | null;
  error: string | null;
  stale: boolean;
};

export type PaperSourcesState = {
  summary: PaperSourceSlot<PaperValidationSummary>;
  eligibility: PaperSourceSlot<PaperEligibilityReport>;
  scheduler: PaperSourceSlot<PaperSchedulerStatus>;
  alerts: PaperSourceSlot<{ items: PaperAlert[] }>;
  history: PaperSourceSlot<{ items: PaperRuntimeHistoryRecord[] }>;
  signals: PaperSourceSlot<{ items: PaperSignalResult[] }>;
  trades: PaperSourceSlot<{ items: PaperTradeRecord[] }>;
};

export const PAPER_SOURCE_LABELS: Record<PaperSourceKey, string> = {
  summary: "Paper validation summary",
  eligibility: "Paper eligibility",
  scheduler: "Scheduler status",
  alerts: "Paper alerts",
  history: "Runtime history",
  signals: "Paper signals",
  trades: "Paper trades",
};

export const PAPER_SOURCE_KEYS: PaperSourceKey[] = [
  "summary",
  "eligibility",
  "scheduler",
  "alerts",
  "history",
  "signals",
  "trades",
];

export function paperSourceTestId(key: PaperSourceKey): string {
  return `strategy-paper-source-${key.replace(/_/g, "-")}`;
}

function idleSlot<T>(): PaperSourceSlot<T> {
  return { status: "idle", data: null, error: null, stale: false };
}

export function initialPaperSourcesState(): PaperSourcesState {
  return {
    summary: idleSlot(),
    eligibility: idleSlot(),
    scheduler: idleSlot(),
    alerts: idleSlot(),
    history: idleSlot(),
    signals: idleSlot(),
    trades: idleSlot(),
  };
}

function isEmptyItems(result: SourceResult<{ items: unknown[] }>): boolean {
  return result.available && (result.data?.items.length ?? 0) === 0;
}

function isEmptySummary(result: SourceResult<PaperValidationSummary>): boolean {
  return result.available && (result.data?.runs.length ?? 0) === 0;
}

function resultToStatus<T>(
  result: SourceResult<T>,
  isEmpty: (value: SourceResult<T>) => boolean,
): PaperSourceStatus {
  if (!result.available) return "failed";
  return isEmpty(result) ? "empty" : "ready";
}

function hadSnapshot<T>(slot: PaperSourceSlot<T>): boolean {
  return (
    slot.status === "ready" ||
    slot.status === "empty" ||
    slot.status === "failed" ||
    slot.data !== null
  );
}

function loadingPatch(
  current: PaperSourceSlot<unknown>,
  mode: RefreshMode,
): PaperSourceSlot<unknown> {
  return {
    status: "loading",
    data: mode === "refresh" ? null : current.data,
    error: null,
    stale: mode === "refresh" && hadSnapshot(current),
  };
}

function waitingForSummaryPatch(): PaperSourceSlot<unknown> {
  return {
    status: "waiting",
    data: null,
    error: "Waiting for paper validation summary.",
    stale: false,
  };
}

type RefreshMode = "initial" | "refresh";

type UseStrategyPaperSourcesArgs = {
  strategyId: string;
  strategyReady: boolean;
};

export function useStrategyPaperSources({
  strategyId,
  strategyReady,
}: UseStrategyPaperSourcesArgs) {
  const [sources, setSources] = useState<PaperSourcesState>(initialPaperSourcesState);
  const sourcesRef = useRef(sources);
  sourcesRef.current = sources;

  const generationRef = useRef(0);
  const initialLoadedForIdRef = useRef<string | null>(null);
  const refreshInFlightRef = useRef(false);

  const isCurrentGeneration = useCallback((gen: number) => gen === generationRef.current, []);

  const patchSource = useCallback(
    <K extends PaperSourceKey>(
      key: K,
      patch: Partial<PaperSourceSlot<PaperSourcesState[K]["data"]>>,
    ) => {
      setSources((prev) => {
        const next = {
          ...prev,
          [key]: { ...prev[key], ...patch },
        };
        sourcesRef.current = next;
        return next;
      });
    },
    [],
  );

  const applySourceResult = useCallback(
    <K extends PaperSourceKey>(
      key: K,
      result: SourceResult<NonNullable<PaperSourcesState[K]["data"]>>,
      isEmpty: (value: SourceResult<NonNullable<PaperSourcesState[K]["data"]>>) => boolean,
      gen: number,
    ) => {
      if (!isCurrentGeneration(gen)) return;
      patchSource(key, {
        status: resultToStatus(result, isEmpty),
        data: result.available ? result.data : null,
        error: result.available ? null : result.error ?? "Request failed",
        stale: false,
      });
    },
    [isCurrentGeneration, patchSource],
  );

  const loadSummaryDependent = useCallback(
    async (gen: number, summaryResult: SourceResult<PaperValidationSummary>, mode: RefreshMode) => {
      const summaryReady = summaryResult.available;
      const runId = summaryResult.data?.runs[0]?.id;
      const waitingMessage =
        "Waiting for paper validation summary before loading dependent sources.";

      if (!summaryReady) {
        if (!isCurrentGeneration(gen)) return;
        patchSource("signals", {
          status: "waiting",
          data: null,
          error: waitingMessage,
          stale: false,
        });
        patchSource("trades", {
          status: "waiting",
          data: null,
          error: waitingMessage,
          stale: false,
        });
      } else if (!runId) {
        if (!isCurrentGeneration(gen)) return;
        patchSource("signals", { status: "empty", data: { items: [] }, error: null, stale: false });
        patchSource("trades", { status: "empty", data: { items: [] }, error: null, stale: false });
      } else {
        setSources((prev) => {
          const next: PaperSourcesState = {
            ...prev,
            signals: loadingPatch(prev.signals, mode) as PaperSourcesState["signals"],
            trades: loadingPatch(prev.trades, mode) as PaperSourcesState["trades"],
          };
          sourcesRef.current = next;
          return next;
        });

        const [signals, trades] = await Promise.all([
          loadSource(api.strategies.paperValidationSignals(runId)),
          loadSource(api.strategies.paperValidationTrades(runId)),
        ]);
        applySourceResult("signals", signals, isEmptyItems, gen);
        applySourceResult("trades", trades, isEmptyItems, gen);
      }

      setSources((prev) => {
        const next: PaperSourcesState = {
          ...prev,
          history: loadingPatch(prev.history, mode) as PaperSourcesState["history"],
        };
        sourcesRef.current = next;
        return next;
      });

      const history = await loadSource(
        runId
          ? api.strategies.schedulerHistory({ run_id: runId, limit: 10 })
          : api.strategies.schedulerHistory({ limit: 10 }),
      );
      applySourceResult("history", history, isEmptyItems, gen);
    },
    [applySourceResult, isCurrentGeneration, patchSource],
  );

  const refreshAllPaperSources = useCallback(
    async (mode: RefreshMode) => {
      if (refreshInFlightRef.current) return;
      refreshInFlightRef.current = true;
      const gen = ++generationRef.current;

      setSources((prev) => {
        const next: PaperSourcesState = {
          summary: loadingPatch(prev.summary, mode) as PaperSourcesState["summary"],
          eligibility: loadingPatch(prev.eligibility, mode) as PaperSourcesState["eligibility"],
          scheduler: loadingPatch(prev.scheduler, mode) as PaperSourcesState["scheduler"],
          alerts: loadingPatch(prev.alerts, mode) as PaperSourcesState["alerts"],
          history: waitingForSummaryPatch() as PaperSourcesState["history"],
          signals: waitingForSummaryPatch() as PaperSourcesState["signals"],
          trades: waitingForSummaryPatch() as PaperSourcesState["trades"],
        };
        sourcesRef.current = next;
        return next;
      });

      try {
        const summaryPromise = loadSource(api.strategies.paperValidation(strategyId));
        const eligibilityPromise = loadSource(api.strategies.paperEligibility(strategyId));
        const schedulerPromise = loadSource(api.strategies.schedulerStatus());
        const alertsPromise = loadSource(api.alerts.list({ limit: 10 }));

        void summaryPromise.then((result) => {
          applySourceResult("summary", result, isEmptySummary, gen);
          void loadSummaryDependent(gen, result, mode);
        });

        void eligibilityPromise.then((result) => {
          applySourceResult("eligibility", result, () => false, gen);
        });

        void schedulerPromise.then((result) => {
          applySourceResult("scheduler", result, () => false, gen);
        });

        void alertsPromise.then((result) => {
          applySourceResult("alerts", result, isEmptyItems, gen);
        });

        await Promise.all([summaryPromise, eligibilityPromise, schedulerPromise, alertsPromise]);
      } finally {
        if (isCurrentGeneration(gen)) {
          refreshInFlightRef.current = false;
        }
      }
    },
    [applySourceResult, isCurrentGeneration, loadSummaryDependent, strategyId],
  );

  const loadSingleSource = useCallback(
    async (key: PaperSourceKey, mode: RefreshMode) => {
      const gen = generationRef.current;
      setSources((prev) => {
        const next: PaperSourcesState = {
          ...prev,
          [key]: loadingPatch(prev[key], mode) as PaperSourcesState[typeof key],
        };
        sourcesRef.current = next;
        return next;
      });

      if (key === "summary") {
        const result = await loadSource(api.strategies.paperValidation(strategyId));
        applySourceResult("summary", result, isEmptySummary, gen);
        setSources((prev) => ({
          ...prev,
          history: waitingForSummaryPatch() as PaperSourcesState["history"],
          signals: waitingForSummaryPatch() as PaperSourcesState["signals"],
          trades: waitingForSummaryPatch() as PaperSourcesState["trades"],
        }));
        await loadSummaryDependent(gen, result, mode);
        return;
      }

      if (key === "eligibility") {
        const result = await loadSource(api.strategies.paperEligibility(strategyId));
        applySourceResult("eligibility", result, () => false, gen);
        return;
      }

      if (key === "scheduler") {
        const result = await loadSource(api.strategies.schedulerStatus());
        applySourceResult("scheduler", result, () => false, gen);
        return;
      }

      if (key === "alerts") {
        const result = await loadSource(api.alerts.list({ limit: 10 }));
        applySourceResult("alerts", result, isEmptyItems, gen);
        return;
      }

      const summary = sourcesRef.current.summary;
      if (
        summary.status === "loading" ||
        summary.status === "idle" ||
        summary.status === "waiting"
      ) {
        if (!isCurrentGeneration(gen)) return;
        patchSource(key, {
          status: "waiting",
          data: null,
          error: "Waiting for paper validation summary.",
          stale: false,
        });
        return;
      }

      if (summary.status === "failed") {
        if (!isCurrentGeneration(gen)) return;
        patchSource(key, {
          status: "waiting",
          data: null,
          error: "Waiting for paper validation summary.",
          stale: false,
        });
        return;
      }

      const runId = summary.data?.runs[0]?.id;

      if (key === "history") {
        const result = await loadSource(
          runId
            ? api.strategies.schedulerHistory({ run_id: runId, limit: 10 })
            : api.strategies.schedulerHistory({ limit: 10 }),
        );
        applySourceResult("history", result, isEmptyItems, gen);
        return;
      }

      if (!runId) {
        if (!isCurrentGeneration(gen)) return;
        patchSource(key, { status: "empty", data: { items: [] }, error: null, stale: false });
        return;
      }

      const result =
        key === "signals"
          ? await loadSource(api.strategies.paperValidationSignals(runId))
          : await loadSource(api.strategies.paperValidationTrades(runId));
      if (key === "signals") {
        applySourceResult("signals", result as SourceResult<{ items: PaperSignalResult[] }>, isEmptyItems, gen);
      } else {
        applySourceResult("trades", result as SourceResult<{ items: PaperTradeRecord[] }>, isEmptyItems, gen);
      }
    },
    [applySourceResult, isCurrentGeneration, loadSummaryDependent, patchSource, strategyId],
  );

  const retryPaperSource = useCallback(
    (key: PaperSourceKey) => {
      void loadSingleSource(key, "refresh");
    },
    [loadSingleSource],
  );

  useEffect(() => {
    generationRef.current += 1;
    initialLoadedForIdRef.current = null;
    refreshInFlightRef.current = false;
    const reset = initialPaperSourcesState();
    sourcesRef.current = reset;
    setSources(reset);
  }, [strategyId]);

  useEffect(() => {
    if (!strategyReady) return;
    if (initialLoadedForIdRef.current === strategyId) return;
    initialLoadedForIdRef.current = strategyId;
    void refreshAllPaperSources("initial");
  }, [strategyReady, strategyId, refreshAllPaperSources]);

  const anyPaperSourceLoading = PAPER_SOURCE_KEYS.some(
    (key) => sources[key].status === "loading",
  );

  return {
    sources,
    refreshAllPaperSources,
    retryPaperSource,
    anyPaperSourceLoading,
  };
}

export function paperSourcePresentation(source: PaperSourceSlot<unknown>): {
  tone: PaperSourceStatus | "idle";
  message: string;
} {
  if (source.status === "idle") {
    return { tone: "idle", message: "Waiting for strategy record…" };
  }
  if (source.status === "loading") {
    return {
      tone: "loading",
      message: source.stale ? "Reloading… previous snapshot cleared." : "Loading…",
    };
  }
  if (source.status === "waiting") {
    return {
      tone: "waiting",
      message: source.error ?? "Waiting for validation summary…",
    };
  }
  if (source.status === "failed") {
    return {
      tone: "failed",
      message: `Unavailable${source.error ? `: ${source.error}` : "."}`,
    };
  }
  if (source.status === "empty") {
    return { tone: "empty", message: "Loaded — empty." };
  }
  return { tone: "ready", message: "Loaded." };
}
