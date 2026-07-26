"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { KillSwitchButton } from "@/components/KillSwitchButton";
import { NarrativePanel } from "@/components/NarrativePanel";
import { RiskBadge } from "@/components/RiskBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { TradingAnalysisPanel } from "@/components/TradingAnalysisPanel";
import {
  PlanSummary,
  WorkflowFreshnessAdapter,
  buildPlanHierarchy,
} from "@/components/workflows";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { RiskBlock } from "@/components/ui/risk-block";
import {
  isPaperModeConfirmed,
  PaperModeIndicator,
} from "@/components/ui/paper-mode-indicator";
import { ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { AgentMessageResponse } from "@/lib/api/types";

async function settled<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

type PlanHubData = {
  proposals: Awaited<ReturnType<typeof api.proposals.list>>;
  approvals: Awaited<ReturnType<typeof api.approvals.list>>;
};

export default function WorkspacePage() {
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const [message, setMessage] = useState("");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [response, setResponse] = useState<AgentMessageResponse | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [assistOpen, setAssistOpen] = useState(false);

  const loader = useCallback(async (): Promise<PlanHubData> => {
    const [proposals, approvals] = await Promise.all([
      settled(api.proposals.list({ limit: 50 }), { items: [], total: 0, limit: 50, offset: 0 }),
      settled(api.approvals.list({ limit: 50 }), { items: [], total: 0, limit: 50, offset: 0 }),
    ]);
    return { proposals, approvals };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const plan = useMemo(
    () =>
      buildPlanHierarchy({
        proposals: data?.proposals.items ?? [],
        approvals: data?.approvals.items ?? [],
      }),
    [data],
  );

  const pendingApprovals =
    data?.approvals.items.filter(
      (item) => item.status === "pending" || item.status === "needs_more_analysis",
    ).length ?? 0;

  async function sendMessage() {
    if (!message.trim() || killSwitchActive) return;
    if (response?.risk_result?.action === "block") return;
    setChatLoading(true);
    setChatError(null);
    try {
      const result = await api.chat.message({
        message,
        conversation_id: conversationId,
        symbol,
        timeframe,
      });
      setResponse(result);
      setConversationId(result.conversation_id);
      setMessage("");
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setChatLoading(false);
    }
  }

  const paperConfirmed = isPaperModeConfirmed(executionMode, realTradingEnabled);
  const freshnessTimestamps = [
    ...(data?.proposals.items.map((item) => item.created_at) ?? []),
    ...(data?.approvals.items.map((item) => item.created_at) ?? []),
  ];

  return (
    <div className="space-y-section" data-testid="plan-hub-page">
      <WorkflowFreshnessAdapter timestamps={freshnessTimestamps} />

      <PageHeader
        title="Plan"
        description="What trade am I preparing, and is it approved? Paper planning only."
        meta={<PaperModeIndicator active={paperConfirmed} />}
      />

      <div className="flex flex-wrap items-center gap-2" data-testid="plan-hub-safety">
        <StatusBadge
          label={`${executionMode ?? "unverified"} mode`}
          tone={executionMode === "paper" ? "paper" : "warn"}
        />
        <StatusBadge label={`providers: ${providerMode}`} tone="muted" />
        {realTradingEnabled === false ? (
          <StatusBadge label="Real trading disabled" tone="healthy" />
        ) : (
          <StatusBadge
            label={realTradingEnabled ? "Real trading enabled" : "Real trading unverified"}
            tone="blocked"
          />
        )}
        <StatusBadge
          label={`${pendingApprovals} awaiting approval`}
          tone={pendingApprovals > 0 ? "warn" : "muted"}
        />
        <KillSwitchButton />
      </div>

      {killSwitchActive ? (
        <ErrorState message="Kill switch is active. Agent requests are paused until you reset it." />
      ) : null}

      <nav aria-label="Plan hub sections" className="flex flex-wrap gap-3 text-sm">
        <Link href="/workspace" className="font-medium text-text-primary underline">
          Plan hub
        </Link>
        <Link href="/proposals" className="text-text-secondary underline">
          Proposals
        </Link>
        <Link href="/approvals" className="text-text-secondary underline">
          Approvals
        </Link>
        <Link href="/pre-trade" className="text-text-secondary underline">
          Pre-Trade
        </Link>
        <Link href="/manual-levels" className="text-text-secondary underline">
          Manual Levels
        </Link>
        <Link href="/strategy-lab" className="text-text-secondary underline">
          Strategy Lab
        </Link>
      </nav>

      {loading ? (
        <LoadingState label="Loading plan hub…" />
      ) : (
        <PlanSummary
          plan={plan}
          error={error}
          onRetry={() => void reload()}
        />
      )}

      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={() => setAssistOpen((open) => !open)}>
          {assistOpen ? "Hide AI assist" : "New plan / AI assist"}
        </Button>
        <Link
          href="/proposals"
          className="inline-flex h-10 items-center rounded-control border border-border bg-surface-1 px-4 text-sm font-medium text-text-primary hover:bg-surface-2"
        >
          Browse proposals
        </Link>
      </div>

      {assistOpen ? (
        <Card data-testid="plan-hub-ai-assist">
          <CardHeader>
            <CardTitle>AI assistance</CardTitle>
            <p className="text-sm text-text-muted">
              Embedded ticket assist. Sensitive actions still require approval. No live orders.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {response?.risk_result?.action === "block" ? (
              <RiskBlock
                reason={
                  response.risk_result.summary ||
                  "Risk engine BLOCKED this request. No override is available."
                }
                ruleReference={response.risk_result.triggered_rules[0]?.rule_id}
              />
            ) : null}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="symbol">Symbol</Label>
                <Input
                  id="symbol"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  disabled={response?.risk_result?.action === "block"}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timeframe">Timeframe</Label>
                <Input
                  id="timeframe"
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  disabled={response?.risk_result?.action === "block"}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="message">Message</Label>
              <Textarea
                id="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Ask for a disciplined trade plan review…"
                disabled={response?.risk_result?.action === "block"}
              />
            </div>
            <Button
              disabled={
                chatLoading ||
                killSwitchActive ||
                response?.risk_result?.action === "block"
              }
              onClick={() => void sendMessage()}
            >
              {chatLoading ? "Sending…" : "Send message"}
            </Button>
            {chatLoading ? <LoadingState label="Waiting for agent response…" /> : null}
            {chatError ? <ErrorState message={chatError} /> : null}
          </CardContent>
        </Card>
      ) : null}

      {response ? (
        <div className="space-y-4">
          {response.analysis ? <TradingAnalysisPanel analysis={response.analysis} /> : null}
          {response.narrative ? (
            <NarrativePanel
              narrative={response.narrative}
              narrativeMeta={response.narrative_meta}
              analysis={response.analysis}
            />
          ) : null}

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>Combined reply</CardTitle>
                <RiskBadge level={response.risk_level} />
                <ConfidenceBadge value={response.confidence} />
                <StatusBadge label={response.approval_status} tone="pending" />
                {response.approval_required ? (
                  <StatusBadge label="Approval required" tone="warn" />
                ) : null}
                {response.analysis ? (
                  <StatusBadge
                    label={`Market: ${response.analysis.market_data_quality}`}
                    tone={response.analysis.market_data_quality === "live" ? "healthy" : "paper"}
                  />
                ) : null}
                {response.narrative_meta ? (
                  <StatusBadge
                    label={
                      response.narrative_meta.source === "llm"
                        ? "Narrative: LLM"
                        : "Narrative: fallback"
                    }
                    tone={response.narrative_meta.source === "llm" ? "healthy" : "warn"}
                  />
                ) : null}
              </div>
              <p className="text-xs text-text-muted">
                Full text reply for chat history. Decisions come from deterministic analysis above.
              </p>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-text-secondary">
              <p className="whitespace-pre-wrap">{response.reply}</p>
              <div className="grid gap-2 text-text-muted md:grid-cols-2">
                {response.proposal_id ? <span>Proposal ID: {response.proposal_id}</span> : null}
                {response.approval_id ? <span>Approval ID: {response.approval_id}</span> : null}
                <span>Request ID: {response.request_id}</span>
                {response.usage ? (
                  <span>
                    Usage: {response.usage.provider} · {response.usage.total_tokens} tokens
                    {response.usage.fallback_used ? " (fallback)" : ""}
                  </span>
                ) : null}
              </div>
              {response.approval_reason ? (
                <p className="text-amber-300">{response.approval_reason}</p>
              ) : null}
              {response.limitations.length ? (
                <div>
                  <p className="mb-2 font-medium text-text-primary">Limitations</p>
                  <ul className="list-disc space-y-1 pl-5 text-text-muted">
                    {response.limitations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
