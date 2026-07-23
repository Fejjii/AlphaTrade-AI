"use client";

import { useState } from "react";

import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { KillSwitchButton } from "@/components/KillSwitchButton";
import { RiskBadge } from "@/components/RiskBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { NarrativePanel } from "@/components/NarrativePanel";
import { TradingAnalysisPanel } from "@/components/TradingAnalysisPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { ErrorState, LoadingState } from "@/components/states";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { api } from "@/lib/api";
import type { AgentMessageResponse } from "@/lib/api/types";

export default function WorkspacePage() {
  const { killSwitchActive } = useAppContext();
  const { executionMode, realTradingEnabled, providerMode } = useSafetyPosture();
  const [message, setMessage] = useState("");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [response, setResponse] = useState<AgentMessageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage() {
    if (!message.trim() || killSwitchActive) return;
    setLoading(true);
    setError(null);
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
      setError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">AI Trading Workspace</h1>
          <p className="text-sm text-zinc-400">
            Chat with the agent. Sensitive actions require approval. Paper mode only.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
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
          </div>
        </div>
        <KillSwitchButton />
      </div>

      {killSwitchActive ? (
        <ErrorState message="Kill switch is active. Agent requests are paused until you reset it." />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Chat</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="symbol">Symbol</Label>
              <Input id="symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timeframe">Timeframe</Label>
              <Input id="timeframe" value={timeframe} onChange={(e) => setTimeframe(e.target.value)} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="message">Message</Label>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask for a disciplined trade plan review…"
            />
          </div>
          <Button disabled={loading || killSwitchActive} onClick={() => void sendMessage()}>
            {loading ? "Sending…" : "Send message"}
          </Button>
          {loading ? <LoadingState label="Waiting for agent response…" /> : null}
          {error ? <ErrorState message={error} /> : null}
        </CardContent>
      </Card>

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
              <p className="text-xs text-zinc-500">
                Full text reply for chat history. Decisions come from deterministic analysis above.
              </p>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-zinc-300">
              <p className="whitespace-pre-wrap">{response.reply}</p>
              <div className="grid gap-2 text-zinc-400 md:grid-cols-2">
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
                  <p className="mb-2 font-medium text-zinc-200">Limitations</p>
                  <ul className="list-disc space-y-1 pl-5 text-zinc-400">
                    {response.limitations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {response.citations.length ? (
                <div>
                  <p className="mb-2 font-medium text-zinc-200">Citations</p>
                  <div className="space-y-2">
                    {response.citations.map((citation) => (
                      <div key={citation.chunk_id} className="rounded-lg border border-zinc-800 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <p>{citation.title ?? citation.document_id}</p>
                          {citation.score != null ? (
                            <StatusBadge label={`score ${citation.score.toFixed(2)}`} tone="muted" />
                          ) : null}
                        </div>
                        <p className="text-zinc-500">{citation.snippet}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {response.tool_outputs.length ? (
                <div>
                  <p className="mb-2 font-medium text-zinc-200">Tool outputs</p>
                  <pre className="overflow-x-auto rounded-lg bg-zinc-950 p-3 text-xs text-zinc-400">
                    {JSON.stringify(response.tool_outputs, null, 2)}
                  </pre>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
