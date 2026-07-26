"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  SignalsInbox,
  WorkflowFreshnessAdapter,
  buildInboxSignals,
  type InboxSignalModel,
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
      tradingView: Awaited<ReturnType<typeof api.tradingview.listSignals>>;
      alerts: Awaited<ReturnType<typeof api.alerts.list>>;
      setupReviews: Awaited<ReturnType<typeof api.alerts.setupReview>>;
      watcherSummary: Awaited<ReturnType<typeof api.marketWatcher.summary>> | null;
    };

async function settled<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

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

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [sessionDismissed, setSessionDismissed] = useState<Set<string>>(new Set());

  const loader = useCallback(async (): Promise<SignalsLoadResult> => {
    try {
      const [tradingView, alerts, setupReviews, watcherSummary] = await Promise.all([
        api.tradingview.listSignals({ limit: 50 }),
        settled(api.alerts.list({ limit: 50 }), { items: [], total: 0 }),
        settled(api.alerts.setupReview({ limit: 50 }), {
          items: [],
          total: 0,
          limit: 50,
          offset: 0,
        }),
        settled(api.marketWatcher.summary(), null),
      ]);
      return { forbidden: false, tradingView, alerts, setupReviews, watcherSummary };
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
      tradingViewSignals: data.tradingView.items,
      alerts: data.alerts.items,
      setupReviews: data.setupReviews.items,
      watcherSummary: data.watcherSummary,
      sessionDismissedIds: sessionDismissed,
    });
  }, [data, sessionDismissed]);

  const selectedSignal = useMemo(() => {
    if (!inboxSignals.length) return null;
    if (selectedId) {
      return inboxSignals.find((item) => item.id === selectedId) ?? inboxSignals[0];
    }
    if (deepLinkSignalId) {
      return (
        inboxSignals.find((item) => item.tradingViewSignalId === deepLinkSignalId) ??
        inboxSignals[0]
      );
    }
    return inboxSignals[0];
  }, [inboxSignals, selectedId, deepLinkSignalId]);

  const selectedTv: TradingViewSignalItem | null =
    data && !data.forbidden && selectedSignal?.tradingViewSignalId
      ? (data.tradingView.items.find((item) => item.id === selectedSignal.tradingViewSignalId) ??
        null)
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
        return;
      }
      setSessionDismissed((prev) => new Set(prev).add(signal.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Dismiss failed.");
    }
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

  const freshnessTimestamps = [
    ...data.tradingView.items.map((item) => item.received_at),
    ...data.alerts.items.map((item) => item.created_at),
    ...data.setupReviews.items.map((item) => item.created_at),
    data.watcherSummary?.last_scan_at ?? null,
    data.watcherSummary?.generated_at ?? null,
  ];

  return (
    <div data-testid="tradingview-signals-page" className="space-y-section">
      <WorkflowFreshnessAdapter timestamps={freshnessTimestamps} />

      <PageHeader
        title="Signals"
        description="Inbox for TradingView, alerts, watcher, and setup review. Paper triage only — never creates live orders."
        meta={<VerifiedPaperModeIndicator />}
      />

      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/alerts" className="underline text-text-secondary">
          Alerts
        </Link>
        <Link href="/alerts/review" className="underline text-text-secondary">
          Setup review
        </Link>
        <Link href="/watcher" className="underline text-text-secondary">
          Watcher scanner
        </Link>
        <Link href="/market-watcher" className="underline text-text-secondary">
          Market watcher
        </Link>
        <Link href="/paper-signal-orchestration" className="underline text-text-secondary">
          Advanced orchestration
        </Link>
      </div>

      {actionError ? (
        <p className="text-sm text-rose-300" role="alert">
          {actionError}
        </p>
      ) : null}

      <SignalsInbox
        signals={inboxSignals}
        selectedId={selectedSignal?.id ?? null}
        onSelect={(signal) => setSelectedId(signal.id)}
        onReviewEvidence={(signal) => {
          if (signal.detailHref) router.push(signal.detailHref);
        }}
        onCreateDraft={(signal) => {
          if (signal.source === "setup_review") {
            router.push("/alerts/review");
            return;
          }
          if (signal.tradingViewSignalId && selectedTv) {
            // Keep user on detail confirmation for TradingView candidate creation.
            setSelectedId(signal.id);
            return;
          }
          router.push(signal.validateHref ?? "/paper-validation/drafts");
        }}
        onPlanTrade={() => router.push("/workspace")}
        onDismiss={(signal, reason) => void dismissSignal(signal, reason)}
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
                <Link href="/workspace" className="text-sky-400 underline">
                  Plan trade
                </Link>
              </div>

              {selectedTv.status === "validated" && !selectedTv.links.candidate_id ? (
                <div className="space-y-2 border-t border-border-subtle pt-4">
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

      {data.tradingView.items.length === 0 && inboxSignals.length === 0 ? (
        <p className="sr-only">No TradingView signals</p>
      ) : null}
    </div>
  );
}
