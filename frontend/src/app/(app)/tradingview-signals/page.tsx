"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  SignalsInbox,
  WorkflowFreshnessAdapter,
  buildInboxSignals,
  buildPlanHref,
  loadSource,
  type InboxSignalModel,
  type SourceResult,
} from "@/components/workflows";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { VerifiedPaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { ErrorState, LoadingState, UnavailableState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api, ApiError, CREATE_TRADINGVIEW_PAPER_CANDIDATE } from "@/lib/api";
import type { TradingViewSignalItem } from "@/lib/api/types";

type SignalsLoadResult =
  | { forbidden: true }
  | {
      forbidden: false;
      tradingView: SourceResult<Awaited<ReturnType<typeof api.tradingview.listSignals>>>;
      alerts: SourceResult<Awaited<ReturnType<typeof api.alerts.list>>>;
      setupReviews: SourceResult<Awaited<ReturnType<typeof api.alerts.setupReview>>>;
      watcherSummary: SourceResult<Awaited<ReturnType<typeof api.marketWatcher.summary>>>;
    };

function statusVariant(
  status: TradingViewSignalItem["status"],
): "success" | "warning" | "danger" | "muted" {
  switch (status) {
    case "validated":
    case "candidate_created":
      return "success";
    case "rejected":
      return "danger";
    case "duplicate":
      return "warning";
    default:
      return "muted";
  }
}

export default function TradingViewSignalsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const deepLinkSignalId = searchParams.get("signal");
  const confirmSectionRef = useRef<HTMLDivElement>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [sessionDismissed, setSessionDismissed] = useState<Set<string>>(new Set());
  const [deepLinkMissing, setDeepLinkMissing] = useState(false);

  const loader = useCallback(async (): Promise<SignalsLoadResult> => {
    try {
      // Preserve explicit forbidden semantics for TradingView.
      const tv = await api.tradingview.listSignals({ limit: 50 });
      const [alerts, setupReviews, watcherSummary] = await Promise.all([
        loadSource(api.alerts.list({ limit: 50 })),
        loadSource(api.alerts.setupReview({ limit: 50 })),
        loadSource(api.marketWatcher.summary()),
      ]);
      return {
        forbidden: false,
        tradingView: { data: tv, available: true, error: null, fallbackUsed: false },
        alerts,
        setupReviews,
        watcherSummary,
      };
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        return { forbidden: true };
      }
      throw error;
    }
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const inboxSignals = useMemo(() => {
    if (!data || data.forbidden) return [];
    return buildInboxSignals({
      tradingViewSignals: data.tradingView.available ? data.tradingView.data?.items : [],
      alerts: data.alerts.available ? data.alerts.data?.items : [],
      setupReviews: data.setupReviews.available ? data.setupReviews.data?.items : [],
      watcherSummary: data.watcherSummary.available ? data.watcherSummary.data : null,
      sessionDismissedIds: sessionDismissed,
    });
  }, [data, sessionDismissed]);

  useEffect(() => {
    if (!data || data.forbidden) return;
    if (!deepLinkSignalId) {
      setDeepLinkMissing(false);
      return;
    }
    const match = inboxSignals.find(
      (item) => item.tradingViewSignalId === deepLinkSignalId,
    );
    if (match) {
      setSelectedId(match.id);
      setDeepLinkMissing(false);
      return;
    }
    // Do not fall back to an unrelated first signal.
    setDeepLinkMissing(true);
    setSelectedId(null);
  }, [data, deepLinkSignalId, inboxSignals]);

  const selectedSignal = useMemo(() => {
    if (!inboxSignals.length) return null;
    if (selectedId) {
      return inboxSignals.find((item) => item.id === selectedId) ?? null;
    }
    if (deepLinkMissing) return null;
    return inboxSignals[0] ?? null;
  }, [inboxSignals, selectedId, deepLinkMissing]);

  const selectedTv: TradingViewSignalItem | null =
    data && !data.forbidden && selectedSignal?.tradingViewSignalId && data.tradingView.data
      ? (data.tradingView.data.items.find(
          (item) => item.id === selectedSignal.tradingViewSignalId,
        ) ?? null)
      : null;

  async function createCandidate(signal: TradingViewSignalItem) {
    setActionError(null);
    setActionBusy(true);
    try {
      await api.tradingview.createCandidate(signal.id, { confirm });
      setConfirm("");
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Candidate creation failed.");
    } finally {
      setActionBusy(false);
    }
  }

  async function dismissSignal(signal: InboxSignalModel, reason: string) {
    setActionError(null);
    try {
      if (signal.dismissTarget === "setup_review" && signal.rawAlertId) {
        await api.alerts.updateSetupReview(signal.rawAlertId, {
          review_status: "ignored",
          review_notes: reason,
        });
        await reload();
        return;
      }
      if (signal.dismissTarget === "alert" && signal.rawAlertId) {
        await api.alerts.markRead(signal.rawAlertId);
        await reload();
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Dismiss failed.");
    }
  }

  function hideForSession(signal: InboxSignalModel) {
    setSessionDismissed((prev) => new Set(prev).add(signal.id));
    if (selectedId === signal.id) setSelectedId(null);
  }

  function clearStaleDeepLink() {
    router.replace("/tradingview-signals");
    setDeepLinkMissing(false);
    setSelectedId(null);
  }

  if (loading) return <LoadingState label="Loading TradingView signals…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!data) {
    return <ErrorState message="TradingView signals unavailable." onRetry={() => void reload()} />;
  }
  if (data.forbidden) {
    return (
      <div data-testid="tradingview-signals-forbidden" className="space-y-section">
        <PageHeader title="Signals" meta={<VerifiedPaperModeIndicator />} />
        <UnavailableState message="You do not have permission to view TradingView signals." />
      </div>
    );
  }

  const unavailableSources = [
    !data.tradingView.available ? "TradingView" : null,
    !data.alerts.available ? "Alerts" : null,
    !data.setupReviews.available ? "Setup review" : null,
    !data.watcherSummary.available ? "Watcher" : null,
  ].filter((item): item is string => Boolean(item));
  const partialData = unavailableSources.length > 0;
  const allSourcesOk = unavailableSources.length === 0;

  // Optional sources that failed to load are excluded before aggregation (no freshness
  // meaning). Available sources with missing timestamps still contribute unavailable.
  const freshnessSources = [
    {
      name: "tradingview",
      available: data.tradingView.available,
      required: true,
      timestamp: data.tradingView.data?.items[0]?.received_at ?? null,
    },
    ...[
      {
        name: "alerts",
        available: data.alerts.available,
        required: false as const,
        timestamp: data.alerts.data?.items[0]?.created_at ?? null,
      },
      {
        name: "setup-review",
        available: data.setupReviews.available,
        required: false as const,
        timestamp: data.setupReviews.data?.items[0]?.created_at ?? null,
      },
      {
        name: "watcher",
        available: data.watcherSummary.available,
        required: false as const,
        timestamp: data.watcherSummary.data?.last_scan_at ?? null,
      },
    ].filter((source) => source.available),
  ];

  return (
    <div data-testid="tradingview-signals-page" className="space-y-section">
      <WorkflowFreshnessAdapter sources={freshnessSources} />

      <PageHeader
        title="Signals"
        description="Inbox for TradingView, alerts, watcher, and setup review. Paper triage only — never creates live orders."
        meta={<VerifiedPaperModeIndicator />}
      />

      <div
        className="flex flex-wrap gap-2 text-caption"
        data-testid="signals-source-availability"
      >
        <Badge variant={data.tradingView.available ? "success" : "warning"}>
          TradingView {data.tradingView.available ? "available" : "unavailable"}
        </Badge>
        <Badge variant={data.alerts.available ? "success" : "warning"}>
          Alerts {data.alerts.available ? "available" : "unavailable"}
        </Badge>
        <Badge variant={data.setupReviews.available ? "success" : "warning"}>
          Setup review {data.setupReviews.available ? "available" : "unavailable"}
        </Badge>
        <Badge variant={data.watcherSummary.available ? "success" : "warning"}>
          Watcher {data.watcherSummary.available ? "available" : "unavailable"}
        </Badge>
      </div>

      {actionError ? (
        <p className="text-sm text-rose-300" role="alert">
          {actionError}
        </p>
      ) : null}

      {deepLinkMissing ? (
        <div
          role="alert"
          data-testid="signal-deep-link-missing"
          className="rounded-control border border-warning-border bg-warning-muted/40 px-4 py-3 text-sm"
        >
          <p className="font-medium text-text-primary">
            Requested signal not found or no longer available.
          </p>
          <Button type="button" size="sm" className="mt-2" onClick={clearStaleDeepLink}>
            Clear stale link and return to inbox
          </Button>
        </div>
      ) : null}

      <SignalsInbox
        signals={inboxSignals}
        selectedId={selectedSignal?.id ?? null}
        onSelect={(signal) => {
          setSelectedId(signal.id);
          setDeepLinkMissing(false);
        }}
        onReviewEvidence={(signal) => {
          setSelectedId(signal.id);
          if (signal.source !== "tradingview" && signal.detailHref) {
            router.push(signal.detailHref);
          }
        }}
        onCreateDraft={(signal) => {
          if (signal.source === "setup_review") {
            router.push("/alerts/review");
            return;
          }
          if (signal.tradingViewSignalId) {
            setSelectedId(signal.id);
            queueMicrotask(() => {
              confirmSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
              confirmSectionRef.current?.querySelector("input")?.focus();
            });
          }
        }}
        onPlanTrade={(signal) => {
          router.push(
            signal.planHref ??
              buildPlanHref({
                source: "tradingview",
                signalId: signal.tradingViewSignalId,
              }),
          );
        }}
        onDismiss={(signal, reason) => void dismissSignal(signal, reason)}
        onHideForSession={hideForSession}
        partialData={partialData}
        unavailableSources={unavailableSources}
        emptyTitle={
          allSourcesOk
            ? "No signals need review"
            : "No signals found in the available sources"
        }
        emptyDescription={
          allSourcesOk
            ? "Validated TradingView signals, unread alerts, and setup reviews will appear here."
            : "One or more inbox sources failed. Retry before treating this as a complete empty inbox."
        }
        detail={
          selectedTv ? (
            <section
              data-testid="tradingview-signal-detail"
              className="space-y-4 rounded-control border border-border-subtle bg-surface-0/40 p-5"
              aria-label="Signal detail"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-medium text-text-primary">
                    {selectedTv.symbol} {selectedTv.direction}
                  </h3>
                  <p className="text-sm text-text-muted">
                    {selectedTv.timeframe}
                    {selectedTv.setup_name
                      ? ` · ${selectedTv.setup_name}${
                          selectedTv.setup_version != null ? ` v${selectedTv.setup_version}` : ""
                        }`
                      : ""}
                  </p>
                </div>
                <Badge variant={statusVariant(selectedTv.status)}>{selectedTv.status}</Badge>
              </div>

              {(selectedTv.rejection_reason || selectedTv.validation_errors?.length) && (
                <div
                  data-testid="tradingview-rejection"
                  className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100"
                >
                  <p className="font-medium">
                    {selectedTv.rejection_reason ?? "Validation rejected this signal."}
                  </p>
                  {selectedTv.validation_errors?.length ? (
                    <ul className="mt-1 list-disc pl-5 text-xs text-amber-100/90">
                      {selectedTv.validation_errors.map((err) => (
                        <li key={err}>{err}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              )}

              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-text-muted">Confidence</dt>
                  <dd className="text-text-primary">
                    {selectedTv.confidence != null ? selectedTv.confidence.toFixed(2) : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-text-muted">Trigger</dt>
                  <dd className="text-text-primary">{selectedTv.trigger_level ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-text-muted">Invalidation</dt>
                  <dd className="text-text-primary">{selectedTv.invalidation_level ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-text-muted">Stop / TP</dt>
                  <dd className="text-text-primary">
                    {selectedTv.stop_loss_level ?? "—"} / {selectedTv.take_profit_level ?? "—"}
                  </dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-text-muted">Provenance</dt>
                  <dd className="text-text-primary">
                    TradingView signed webhook · received{" "}
                    {new Date(selectedTv.received_at).toLocaleString()}
                  </dd>
                </div>
              </dl>

              <div className="flex flex-wrap gap-3 text-xs">
                {selectedTv.links.paper_candidate_path ? (
                  <Link
                    href={selectedTv.links.paper_candidate_path}
                    className="text-sky-400 underline"
                  >
                    Paper candidate
                  </Link>
                ) : null}
                {selectedTv.links.strategy_path ? (
                  <Link href={selectedTv.links.strategy_path} className="text-sky-400 underline">
                    Strategy
                  </Link>
                ) : null}
                {selectedTv.links.journal_path ? (
                  <Link href={selectedTv.links.journal_path} className="text-sky-400 underline">
                    Journal trade
                  </Link>
                ) : null}
                <Link
                  href={buildPlanHref({ source: "tradingview", signalId: selectedTv.id })}
                  className="text-sky-400 underline"
                >
                  Plan trade
                </Link>
              </div>

              {selectedTv.status === "validated" && !selectedTv.links.candidate_id ? (
                <div
                  ref={confirmSectionRef}
                  id="create-paper-candidate"
                  className="space-y-2 border-t border-border-subtle pt-4"
                >
                  <p className="text-xs text-text-muted">
                    Optional paper-validation candidate only. Confirm with{" "}
                    <code className="text-text-secondary">{CREATE_TRADINGVIEW_PAPER_CANDIDATE}</code>.
                  </p>
                  <Input
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                    placeholder={CREATE_TRADINGVIEW_PAPER_CANDIDATE}
                    aria-label="Candidate confirmation phrase"
                  />
                  <Button
                    disabled={actionBusy || confirm !== CREATE_TRADINGVIEW_PAPER_CANDIDATE}
                    onClick={() => void createCandidate(selectedTv)}
                  >
                    Create paper candidate
                  </Button>
                </div>
              ) : null}
            </section>
          ) : selectedSignal ? (
            <section
              className="space-y-3 rounded-control border border-border-subtle bg-surface-0/40 p-5"
              aria-label="Signal detail"
            >
              <h3 className="text-lg font-medium text-text-primary">{selectedSignal.title}</h3>
              <p className="text-sm text-text-secondary">{selectedSignal.summary}</p>
              <p className="text-sm text-text-muted">{selectedSignal.provenance}</p>
              <p className="text-sm text-text-secondary">Next action: {selectedSignal.nextAction}</p>
              <div className="flex flex-wrap gap-3 text-sm">
                <Link href={selectedSignal.href} className="underline text-text-secondary">
                  Open source workflow
                </Link>
                {selectedSignal.planHref ? (
                  <Link href={selectedSignal.planHref} className="underline text-text-secondary">
                    Plan trade
                  </Link>
                ) : null}
              </div>
            </section>
          ) : (
            <p className="text-sm text-text-muted">Select a signal to inspect evidence.</p>
          )
        }
      />
    </div>
  );
}
