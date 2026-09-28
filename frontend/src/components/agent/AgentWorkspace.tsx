"use client";

import { ImageIcon, Mic, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  AGENT_CAPABILITIES,
  type AgentCapability,
} from "@/components/agent/agent-contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { useAppContext } from "@/contexts/AppContext";
import { api } from "@/lib/api";
import type {
  AgentMessageResponse,
  ConversationMessageRecord,
  ConversationSummary,
  Position,
  UserStrategy,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

type LoadState<T> = {
  items: T[];
  error: string | null;
  loading: boolean;
};

const emptyLoad = { items: [], error: null, loading: true };

function messageLabel(role: ConversationMessageRecord["role"]): string {
  if (role === "user") return "You";
  if (role === "assistant") return "Agent";
  return "System";
}

function CapabilityList({ items }: { items: readonly AgentCapability[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id} data-capability={item.id} data-status={item.status}>
          <p className="text-sm text-text-primary">{item.label}</p>
          <p className="text-caption text-text-muted">{item.contract}</p>
        </li>
      ))}
    </ul>
  );
}

export function AgentWorkspace() {
  const { killSwitchActive } = useAppContext();
  const [conversations, setConversations] = useState<LoadState<ConversationSummary>>(emptyLoad);
  const [positions, setPositions] = useState<LoadState<Position>>(emptyLoad);
  const [strategies, setStrategies] = useState<LoadState<UserStrategy>>({
    items: [],
    error: null,
    loading: true,
  });
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessageRecord[]>([]);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("");
  const [strategyId, setStrategyId] = useState("");
  const [marketLabel, setMarketLabel] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [latest, setLatest] = useState<AgentMessageResponse | null>(null);

  const refreshConversations = useCallback(async () => {
    setConversations((current) => ({ ...current, loading: true, error: null }));
    try {
      const page = await api.conversations.list({ limit: 30 });
      setConversations({ items: page.items, error: null, loading: false });
    } catch (error) {
      setConversations({
        items: [],
        error: error instanceof Error ? error.message : "Conversations unavailable",
        loading: false,
      });
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
    void api.positions
      .list({ status: "open", limit: 20 })
      .then((page) => setPositions({ items: page.items, error: null, loading: false }))
      .catch((error: unknown) =>
        setPositions({
          items: [],
          error: error instanceof Error ? error.message : "Open positions unavailable",
          loading: false,
        }),
      );
    void api.strategies
      .list({ limit: 50 })
      .then((page) => setStrategies({ items: page.items, error: null, loading: false }))
      .catch((error: unknown) =>
        setStrategies({
          items: [],
          error: error instanceof Error ? error.message : "Strategies unavailable",
          loading: false,
        }),
      );
  }, [refreshConversations]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setMessagesError(null);
      return;
    }
    let cancelled = false;
    void api.conversations
      .listMessages(conversationId, { limit: 100 })
      .then((page) => {
        if (!cancelled) {
          setMessages(page.items);
          setMessagesError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMessagesError(error instanceof Error ? error.message : "Messages unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  useEffect(() => {
    const trimmed = symbol.trim();
    if (!trimmed) {
      setMarketLabel(null);
      return;
    }
    let cancelled = false;
    void api.canonical
      .getMarketStatus({ symbol: trimmed })
      .then((status) => {
        if (!cancelled) setMarketLabel(status.availability);
      })
      .catch(() => {
        if (!cancelled) setMarketLabel("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const blocked = latest?.risk_result?.action === "block";

  async function sendMessage() {
    const text = draft.trim();
    if (!text || sending || killSwitchActive || blocked) return;
    setSending(true);
    setSendError(null);
    try {
      const result = await api.chat.message({
        message: text,
        conversation_id: conversationId ?? undefined,
        symbol: symbol.trim() || undefined,
        timeframe: timeframe.trim() || undefined,
        strategy_id: strategyId || undefined,
      });
      setLatest(result);
      setConversationId(result.conversation_id);
      setDraft("");
      try {
        const page = await api.conversations.listMessages(result.conversation_id, { limit: 100 });
        setMessages(page.items);
        setMessagesError(null);
      } catch {
        setMessages((current) => [
          ...current,
          {
            id: `local-user-${result.request_id}`,
            conversation_id: result.conversation_id,
            organization_id: "",
            user_id: "",
            role: "user",
            content: text,
            created_at: new Date().toISOString(),
          },
          {
            id: `local-agent-${result.request_id}`,
            conversation_id: result.conversation_id,
            organization_id: "",
            user_id: "",
            role: "assistant",
            content: result.reply,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      void refreshConversations();
    } catch (error) {
      setSendError(error instanceof Error ? error.message : "Message failed");
    } finally {
      setSending(false);
    }
  }

  const wired = AGENT_CAPABILITIES.filter((item) => item.status === "wired");
  const missing = AGENT_CAPABILITIES.filter((item) => item.status === "missing");

  return (
    <div className="space-y-4" data-testid="agent-workspace">
      <PageHeader
        title="Agent"
        description="Discuss a paper trade in text. Attachments and voice are not connected yet."
      />

      <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <Card data-testid="agent-history">
          <CardHeader>
            <CardTitle>History</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button
              type="button"
              variant="secondary"
              className="w-full"
              onClick={() => {
                setConversationId(null);
                setMessages([]);
                setLatest(null);
              }}
            >
              New conversation
            </Button>
            {conversations.loading ? <p className="text-caption text-text-muted">Loading…</p> : null}
            {conversations.error ? (
              <p className="text-sm text-danger" data-testid="agent-history-error">
                {conversations.error}
              </p>
            ) : null}
            {!conversations.loading && conversations.items.length === 0 && !conversations.error ? (
              <p className="text-sm text-text-muted">No conversations yet.</p>
            ) : null}
            <ul className="space-y-1">
              {conversations.items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={cn(
                      "w-full rounded-control px-2 py-2 text-left text-sm",
                      item.id === conversationId
                        ? "bg-surface-2 text-text-primary"
                        : "text-text-secondary hover:bg-surface-1",
                    )}
                    onClick={() => setConversationId(item.id)}
                  >
                    {item.title?.trim() || "Untitled"}
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card data-testid="agent-context">
            <CardHeader>
              <CardTitle>Context</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {positions.error ? (
                <p className="text-sm text-text-muted">Open positions unavailable</p>
              ) : positions.items.length === 0 && !positions.loading ? (
                <p className="text-sm text-text-muted">No open paper positions</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {positions.items.map((position) => (
                    <button
                      key={position.id}
                      type="button"
                      className="rounded-control border border-border-subtle px-2 py-1 text-caption text-text-secondary hover:bg-surface-1"
                      onClick={() => setSymbol(position.symbol)}
                    >
                      {position.symbol} · {position.direction}
                    </button>
                  ))}
                </div>
              )}
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <Label htmlFor="agent-symbol">Symbol</Label>
                  <Input
                    id="agent-symbol"
                    value={symbol}
                    onChange={(event) => setSymbol(event.target.value)}
                    placeholder="BTCUSDT"
                  />
                </div>
                <div>
                  <Label htmlFor="agent-timeframe">Timeframe</Label>
                  <Input
                    id="agent-timeframe"
                    value={timeframe}
                    onChange={(event) => setTimeframe(event.target.value)}
                    placeholder="1h"
                  />
                </div>
                <div>
                  <Label htmlFor="agent-strategy">Strategy</Label>
                  <Select
                    id="agent-strategy"
                    value={strategyId}
                    onChange={(event) => setStrategyId(event.target.value)}
                    disabled={Boolean(strategies.error)}
                  >
                    <option value="">None</option>
                    {strategies.items.map((strategy) => (
                      <option key={strategy.id} value={strategy.id}>
                        {strategy.name}
                      </option>
                    ))}
                  </Select>
                  {strategies.error ? (
                    <p className="mt-1 text-caption text-text-muted">Strategies unavailable</p>
                  ) : null}
                </div>
              </div>
              {symbol.trim() ? (
                <p className="text-caption text-text-muted" data-testid="agent-market-context">
                  Market evidence: {marketLabel ?? "…"}
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Conversation</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {messagesError ? <p className="text-sm text-danger">{messagesError}</p> : null}
              <div className="flex max-h-[28rem] flex-col gap-3 overflow-y-auto" data-testid="agent-thread">
                {messages.length === 0 ? (
                  <p className="text-sm text-text-muted">Send a message to start.</p>
                ) : (
                  messages.map((message) => (
                    <div
                      key={message.id}
                      data-testid="agent-message"
                      data-role={message.role}
                      className={cn(
                        "max-w-[90%] rounded-card border px-3 py-2 text-sm",
                        message.role === "user"
                          ? "ml-auto border-border bg-surface-2 text-text-primary"
                          : "mr-auto border-border-subtle bg-surface-0 text-text-secondary",
                      )}
                    >
                      <p className="text-caption text-text-muted">{messageLabel(message.role)}</p>
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    </div>
                  ))
                )}
              </div>

              {latest ? (
                <div className="space-y-1 text-caption text-text-muted" data-testid="agent-latest">
                  {latest.risk_result ? <p>Risk: {latest.risk_result.summary}</p> : null}
                  {latest.citations.length > 0 ? (
                    <p>
                      Citations:{" "}
                      {latest.citations.map((item) => item.title || item.document_id).join(", ")}
                    </p>
                  ) : null}
                  {latest.pending_proposal ? (
                    <p>
                      Proposal preview: {latest.pending_proposal.status}. Confirmation stays outside
                      this workspace.
                    </p>
                  ) : null}
                </div>
              ) : null}

              <form
                className="space-y-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void sendMessage();
                }}
              >
                <Textarea
                  aria-label="Message"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Ask about a paper trade, a rule, or a journal note."
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="submit" disabled={sending || killSwitchActive || blocked || !draft.trim()}>
                    <Send className="h-4 w-4" aria-hidden="true" />
                    {sending ? "Sending…" : "Send"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled
                    data-testid="agent-attach-image"
                    aria-describedby="agent-attachment-contract"
                  >
                    <ImageIcon className="h-4 w-4" aria-hidden="true" />
                    Attach screenshot
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled
                    data-testid="agent-voice"
                    aria-describedby="agent-voice-contract"
                  >
                    <Mic className="h-4 w-4" aria-hidden="true" />
                    Voice
                  </Button>
                </div>
                <p id="agent-attachment-contract" className="text-caption text-text-muted">
                  Screenshot attachment is not available. The chat API accepts text only.
                </p>
                <p id="agent-voice-contract" className="text-caption text-text-muted">
                  Voice is not available. There is no transcription endpoint.
                </p>
                {killSwitchActive ? (
                  <p className="text-sm text-danger">Kill switch is active. New messages are paused.</p>
                ) : null}
                {blocked ? (
                  <p className="text-sm text-danger">Risk blocked further messages in this reply.</p>
                ) : null}
                {sendError ? <p className="text-sm text-danger">{sendError}</p> : null}
              </form>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card data-testid="agent-capability-boundary">
        <CardHeader>
          <CardTitle>What this workspace can do</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 lg:grid-cols-2">
          <div>
            <Badge variant="success">Connected</Badge>
            <div className="mt-3">
              <CapabilityList items={wired} />
            </div>
          </div>
          <div>
            <Badge variant="muted">Not connected</Badge>
            <div className="mt-3">
              <CapabilityList items={missing} />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
