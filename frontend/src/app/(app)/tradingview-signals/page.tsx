"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api, ApiError, CREATE_TRADINGVIEW_PAPER_CANDIDATE } from "@/lib/api";
import type {
  TradingViewSignalItem,
  TradingViewSignalListResponse,
  TradingViewSignalStatus,
} from "@/lib/api/types";

type SignalsLoadResult =
  | { forbidden: true; data: null }
  | { forbidden: false; data: TradingViewSignalListResponse };

function statusVariant(
  status: TradingViewSignalStatus,
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
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const loader = useCallback(async (): Promise<SignalsLoadResult> => {
    try {
      const data = await api.tradingview.listSignals({ limit: 50 });
      return { forbidden: false, data };
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        return { forbidden: true, data: null };
      }
      throw error;
    }
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const selected =
    data?.forbidden === false
      ? (data.data.items.find((item) => item.id === selectedId) ?? data.data.items[0] ?? null)
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

  if (loading) return <LoadingState label="Loading TradingView signals…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!data) {
    return <ErrorState message="TradingView signals unavailable." onRetry={() => void reload()} />;
  }
  if (data.forbidden) {
    return (
      <div data-testid="tradingview-signals-forbidden" className="space-y-3">
        <h1 className="text-2xl font-semibold text-zinc-50">TradingView Signals</h1>
        <p className="text-sm text-zinc-400">You do not have permission to view TradingView signals.</p>
      </div>
    );
  }

  const items = data.data.items;

  return (
    <div data-testid="tradingview-signals-page" className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-50">TradingView Signals</h1>
        <p className="mt-1 max-w-2xl text-sm text-zinc-400">
          Signed webhook intake inbox. Paper validation only — never creates live orders.
        </p>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No TradingView signals"
          description="Validated alerts from TradingView will appear here after signed webhook intake."
        />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <section className="space-y-3" aria-label="Signal inbox">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelectedId(item.id)}
                className={`w-full rounded-lg border px-4 py-3 text-left transition ${
                  selected?.id === item.id
                    ? "border-sky-500/60 bg-sky-500/10"
                    : "border-zinc-800 bg-zinc-950/40 hover:border-zinc-700"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-zinc-100">
                    {item.symbol} · {item.timeframe} · {item.direction}
                  </div>
                  <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                </div>
                <div className="mt-1 text-xs text-zinc-500">
                  Alert {item.external_alert_id} · {new Date(item.received_at).toLocaleString()}
                </div>
              </button>
            ))}
          </section>

          {selected ? (
            <section
              data-testid="tradingview-signal-detail"
              className="space-y-4 rounded-lg border border-zinc-800 bg-zinc-950/30 p-5"
              aria-label="Signal detail"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-medium text-zinc-50">
                    {selected.symbol} {selected.direction}
                  </h2>
                  <p className="text-sm text-zinc-400">
                    {selected.timeframe}
                    {selected.setup_name
                      ? ` · ${selected.setup_name}${
                          selected.setup_version != null ? ` v${selected.setup_version}` : ""
                        }`
                      : ""}
                  </p>
                </div>
                <Badge variant={statusVariant(selected.status)}>{selected.status}</Badge>
              </div>

              {(selected.rejection_reason || selected.validation_errors?.length) && (
                <div
                  data-testid="tradingview-rejection"
                  className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100"
                >
                  <p className="font-medium">
                    {selected.rejection_reason ?? "Validation rejected this signal."}
                  </p>
                  {selected.validation_errors?.length ? (
                    <ul className="mt-1 list-disc pl-5 text-xs text-amber-100/90">
                      {selected.validation_errors.map((err) => (
                        <li key={err}>{err}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              )}

              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-zinc-500">Confidence</dt>
                  <dd className="text-zinc-200">
                    {selected.confidence != null ? selected.confidence.toFixed(2) : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Trigger</dt>
                  <dd className="text-zinc-200">{selected.trigger_level ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Invalidation</dt>
                  <dd className="text-zinc-200">{selected.invalidation_level ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Stop / TP</dt>
                  <dd className="text-zinc-200">
                    {selected.stop_loss_level ?? "—"} / {selected.take_profit_level ?? "—"}
                  </dd>
                </div>
              </dl>

              <div className="flex flex-wrap gap-3 text-xs">
                {selected.links.paper_candidate_path ? (
                  <Link
                    href={selected.links.paper_candidate_path}
                    className="text-sky-400 underline"
                  >
                    Paper candidate
                  </Link>
                ) : null}
                {selected.links.strategy_path ? (
                  <Link href={selected.links.strategy_path} className="text-sky-400 underline">
                    Strategy
                  </Link>
                ) : null}
                {selected.links.journal_path ? (
                  <Link href={selected.links.journal_path} className="text-sky-400 underline">
                    Journal trade
                  </Link>
                ) : null}
              </div>

              {selected.status === "validated" && !selected.links.candidate_id ? (
                <div className="space-y-2 border-t border-zinc-800 pt-4">
                  <p className="text-xs text-zinc-500">
                    Optional paper-validation candidate only. Confirm with{" "}
                    <code className="text-zinc-300">{CREATE_TRADINGVIEW_PAPER_CANDIDATE}</code>.
                  </p>
                  <Input
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                    placeholder={CREATE_TRADINGVIEW_PAPER_CANDIDATE}
                    aria-label="Candidate confirmation phrase"
                  />
                  <Button
                    disabled={actionBusy || confirm !== CREATE_TRADINGVIEW_PAPER_CANDIDATE}
                    onClick={() => void createCandidate(selected)}
                  >
                    Create paper candidate
                  </Button>
                  {actionError ? (
                    <p className="text-sm text-rose-300" role="alert">
                      {actionError}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}
