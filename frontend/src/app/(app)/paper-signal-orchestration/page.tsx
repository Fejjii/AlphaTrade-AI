"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import {
  BlockedState,
  EmptyState,
  ErrorState,
  LoadingState,
  UnavailableState,
} from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { RiskBlock } from "@/components/ui/risk-block";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api, ApiError, APPROVE_PAPER_SIGNAL_PROPOSAL } from "@/lib/api";
import type {
  PaperSignalOrchestrationDecisionItem,
  PaperSignalOrchestrationListResponse,
  PaperSignalOrchestrationStatus,
} from "@/lib/api/types";

type LoadResult =
  | { forbidden: true; data: null }
  | { forbidden: false; data: PaperSignalOrchestrationListResponse };

function statusVariant(
  status: PaperSignalOrchestrationStatus,
): "success" | "warning" | "danger" | "muted" {
  switch (status) {
    case "eligible":
    case "paper_candidate_created":
    case "paper_proposal_created":
      return "success";
    case "awaiting_review":
      return "warning";
    case "blocked":
    case "rejected":
    case "expired":
      return "danger";
    default:
      return "muted";
  }
}

function CheckList({
  title,
  checks,
}: {
  title: string;
  checks: PaperSignalOrchestrationDecisionItem["eligibility_checks"];
}) {
  if (checks.length === 0) {
    return (
      <div>
        <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
        <p className="mt-1 text-sm text-zinc-500">No checks recorded.</p>
      </div>
    );
  }
  return (
    <div>
      <h3 className="text-sm font-medium text-zinc-200">{title}</h3>
      <ul className="mt-2 space-y-2">
        {checks.map((check) => (
          <li key={check.code} className="text-sm text-zinc-400">
            <span className={check.passed ? "text-emerald-400" : "text-rose-400"}>
              {check.passed ? "pass" : "fail"}
            </span>{" "}
            <span className="text-zinc-300">{check.code}</span> — {check.detail}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function PaperSignalOrchestrationPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const loader = useCallback(async (): Promise<LoadResult> => {
    try {
      const data = await api.paperSignalOrchestration.listDecisions({ limit: 50 });
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

  async function approveProposal(decision: PaperSignalOrchestrationDecisionItem) {
    setActionError(null);
    setActionBusy(true);
    try {
      await api.paperSignalOrchestration.approvePaperProposal(decision.id, { confirm });
      setConfirm("");
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setActionBusy(false);
    }
  }

  if (loading) return <LoadingState label="Loading signal orchestration queue…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!data) {
    return (
      <ErrorState message="Signal orchestration unavailable." onRetry={() => void reload()} />
    );
  }
  if (data.forbidden) {
    return (
      <div data-testid="paper-signal-orch-forbidden" className="space-y-section">
        <PageHeader title="Signal Orchestration" meta={<PaperModeIndicator />} />
        <UnavailableState message="You do not have permission to view paper-signal orchestration." />
      </div>
    );
  }

  const items = data.data.items;
  const enabled = data.data.enabled;
  const mode = data.data.mode;

  return (
    <div data-testid="paper-signal-orch-page" className="space-y-section">
      <PageHeader
        title="Signal Orchestration"
        description={
          <>
            Deterministic paper-only routing from validated TradingView signals. Mode:{" "}
            <span className="text-text-primary">{mode}</span>
            {!enabled ? " · disabled (fail-closed)" : ""}. Never creates live orders.
          </>
        }
        meta={<PaperModeIndicator />}
      />

      {!enabled && (
        <div data-testid="paper-signal-orch-disabled">
          <BlockedState message="Orchestration is disabled for this environment. Decisions may be empty until enabled." />
        </div>
      )}

      {items.length === 0 ? (
        <EmptyState
          title="No orchestration decisions"
          description="Evaluate or orchestrate a validated TradingView signal to populate this queue."
        />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <div className="space-y-2" data-testid="paper-signal-orch-queue">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setSelectedId(item.id);
                  setExpanded(false);
                  setActionError(null);
                }}
                className={`w-full rounded-md border px-3 py-3 text-left transition ${
                  selected?.id === item.id
                    ? "border-zinc-500 bg-zinc-900"
                    : "border-zinc-800 bg-zinc-950 hover:border-zinc-700"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-zinc-100">
                    {item.symbol} · {item.timeframe} · {item.direction}
                  </span>
                  <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                </div>
                <p className="mt-1 truncate text-xs text-zinc-500">
                  {item.reason_summary ?? "No summary"}
                </p>
              </button>
            ))}
          </div>

          {selected && (
            <div
              data-testid="paper-signal-orch-detail"
              className="space-y-5 rounded-md border border-zinc-800 bg-zinc-950/60 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-medium text-zinc-50">
                  {selected.symbol} {selected.direction}
                </h2>
                <Badge variant={statusVariant(selected.status)}>{selected.status}</Badge>
                <Badge variant="muted">{selected.mode}</Badge>
              </div>

              <p className="text-sm text-text-secondary">
                {selected.reason_summary ?? "No blocking reason."}
              </p>

              {selected.status === "blocked" ? (
                <RiskBlock
                  reason={selected.reason_summary ?? "Risk checks blocked this paper signal."}
                  ruleReference={selected.reason_codes?.[0]}
                />
              ) : null}

              {(selected.reason_codes?.length ?? 0) > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-zinc-200">Reason codes</h3>
                  <p className="mt-1 text-sm text-zinc-400">
                    {selected.reason_codes?.join(", ")}
                  </p>
                </div>
              )}

              <div className="flex flex-wrap gap-3 text-sm">
                {selected.links.signal_path && (
                  <Link className="text-sky-400 hover:underline" href={selected.links.signal_path}>
                    TradingView signal
                  </Link>
                )}
                {selected.links.candidate_path && (
                  <Link
                    className="text-sky-400 hover:underline"
                    href={selected.links.candidate_path}
                  >
                    Candidate
                  </Link>
                )}
                {selected.links.run_plan_path && (
                  <Link
                    className="text-sky-400 hover:underline"
                    href={selected.links.run_plan_path}
                  >
                    Run plan
                  </Link>
                )}
                {selected.links.proposal_path && (
                  <Link
                    className="text-sky-400 hover:underline"
                    href={selected.links.proposal_path}
                  >
                    Proposal
                  </Link>
                )}
                {selected.links.journal_path && (
                  <Link
                    className="text-sky-400 hover:underline"
                    href={selected.links.journal_path}
                  >
                    Journal
                  </Link>
                )}
              </div>

              <Button
                type="button"
                variant="secondary"
                onClick={() => setExpanded((value) => !value)}
              >
                {expanded ? "Hide checks" : "Show eligibility & risk checks"}
              </Button>

              {expanded && (
                <div className="space-y-5" data-testid="paper-signal-orch-checks">
                  <CheckList title="Eligibility" checks={selected.eligibility_checks} />
                  <CheckList title="Risk" checks={selected.risk_checks} />
                  <div>
                    <h3 className="text-sm font-medium text-zinc-200">Transitions</h3>
                    <ul className="mt-2 space-y-1 text-sm text-zinc-400">
                      {selected.transitions.map((t) => (
                        <li key={`${t.at}-${t.to_status}`}>
                          {t.at}: {t.from_status ?? "∅"} → {t.to_status} ({t.reason})
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {selected.status === "awaiting_review" && (
                <div className="space-y-3 border-t border-zinc-800 pt-4">
                  <p className="text-sm text-zinc-400">
                    Approve creating a paper trade proposal. Does not place orders. Confirm with{" "}
                    <code className="text-zinc-200">{APPROVE_PAPER_SIGNAL_PROPOSAL}</code>.
                  </p>
                  <Input
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                    placeholder={APPROVE_PAPER_SIGNAL_PROPOSAL}
                    aria-label="Approval confirmation phrase"
                  />
                  <Button
                    type="button"
                    disabled={actionBusy || confirm !== APPROVE_PAPER_SIGNAL_PROPOSAL}
                    onClick={() => void approveProposal(selected)}
                  >
                    {actionBusy ? "Approving…" : "Approve paper proposal"}
                  </Button>
                  {actionError && (
                    <p className="text-sm text-rose-400" data-testid="paper-signal-orch-action-error">
                      {actionError}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
