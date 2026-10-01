"use client";

import { ImageIcon, Mic, Send, MessageSquare } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  AGENT_CAPABILITIES,
  type AgentCapability,
} from "@/components/agent/agent-contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { isPaperModeConfirmed } from "@/components/ui/paper-mode-indicator";
import { formatDateTime } from "@/lib/format";
import { PageHeader } from "@/components/ui/page-header";
import { useAppContext } from "@/contexts/AppContext";
import { api } from "@/lib/api";
import type {
  AgentStructuredProposal,
  AgentTurnResult,
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
  const { killSwitchActive, health } = useAppContext();
  const threadRef = useRef<HTMLDivElement>(null);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesRetry, setMessagesRetry] = useState(0);
  const [conversations, setConversations] =
    useState<LoadState<ConversationSummary>>(emptyLoad);
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
  const [latest, setLatest] = useState<AgentTurnResult | null>(null);
  const [proposals, setProposals] = useState<AgentStructuredProposal[]>([]);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const refreshConversations = useCallback(async () => {
    setConversations((current) => ({ ...current, loading: true, error: null }));
    try {
      const page = await api.conversations.list({ limit: 30 });
      setConversations({ items: page.items, error: null, loading: false });
    } catch (error) {
      setConversations({
        items: [],
        error:
          error instanceof Error ? error.message : "Conversations unavailable",
        loading: false,
      });
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
    void api.positions
      .list({ status: "open", limit: 20 })
      .then((page) =>
        setPositions({ items: page.items, error: null, loading: false }),
      )
      .catch((error: unknown) =>
        setPositions({
          items: [],
          error:
            error instanceof Error
              ? error.message
              : "Open positions unavailable",
          loading: false,
        }),
      );
    void api.strategies
      .list({ limit: 50 })
      .then((page) =>
        setStrategies({ items: page.items, error: null, loading: false }),
      )
      .catch((error: unknown) =>
        setStrategies({
          items: [],
          error:
            error instanceof Error ? error.message : "Strategies unavailable",
          loading: false,
        }),
      );
  }, [refreshConversations]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setMessagesError(null);
      setMessagesLoading(false);
      return;
    }
    let cancelled = false;
    setMessages([]);
    setMessagesError(null);
    setMessagesLoading(true);
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
          setMessagesError(
            error instanceof Error ? error.message : "Messages unavailable",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setMessagesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId, messagesRetry]);

  useEffect(() => {
    if (threadRef.current)
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages, sending]);

  useEffect(() => {
    const trimmed = symbol.trim();
    if (!trimmed) {
      setMarketLabel(null);
      return;
    }
    let cancelled = false;
    setMarketLabel(null);
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

  async function sendMessage() {
    const text = draft.trim();
    if (!text || sending || killSwitchActive) return;
    setSending(true);
    setSendError(null);
    try {
      const result = await api.agent.turn({
        message: text,
        conversation_id: conversationId ?? undefined,
        symbol: symbol.trim() || undefined,
        timeframe: timeframe.trim() || undefined,
        strategy_id: strategyId || undefined,
      });
      setLatest(result);
      setProposals(result.proposals);
      setConversationId(result.conversation_id);
      setDraft("");
      try {
        const page = await api.conversations.listMessages(
          result.conversation_id,
          { limit: 100 },
        );
        setMessages(page.items);
        setMessagesError(null);
      } catch {
        setMessages((current) => [
          ...current,
          {
            id: `local-user-${result.conversation_id}`,
            conversation_id: result.conversation_id,
            organization_id: "",
            user_id: "",
            role: "user",
            content: text,
            created_at: new Date().toISOString(),
          },
          {
            id: `local-agent-${result.conversation_id}`,
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

  async function decideProposal(
    proposal: AgentStructuredProposal,
    statement: "I confirm" | "I reject",
  ) {
    if (decidingId) return;
    setDecidingId(proposal.proposal_id);
    setSendError(null);
    try {
      const request = {
        conversation_id: proposal.conversation_id,
        expected_content_hash: proposal.content_hash,
        statement,
      };
      const updated =
        statement === "I confirm"
          ? await api.agent.confirmProposal(proposal.proposal_id, request)
          : await api.agent.rejectProposal(proposal.proposal_id, request);
      setProposals((current) =>
        current.map((item) =>
          item.proposal_id === updated.proposal_id ? updated : item,
        ),
      );
    } catch (error) {
      setSendError(
        error instanceof Error ? error.message : "Proposal decision failed",
      );
    } finally {
      setDecidingId(null);
    }
  }

  const wired = AGENT_CAPABILITIES.filter((item) => item.status === "wired");
  const missing = AGENT_CAPABILITIES.filter(
    (item) => item.status === "missing",
  );

  return (
    <div
      className="space-y-4 [&_input]:text-base [&_select]:text-base [&_textarea]:text-base lg:[&_input]:text-sm lg:[&_select]:text-sm lg:[&_textarea]:text-sm"
      data-testid="agent-workspace"
    >
      <PageHeader
        title="Agent"
        description="Think through a setup, review a decision, or capture a lesson."
        meta={
          <PaperModeIndicator
            active={isPaperModeConfirmed(
              health?.execution_mode,
              health?.real_trading_enabled,
            )}
          />
        }
        actions={
          <>
            <Button
              type="button"
              variant="secondary"
              className="min-h-11"
              disabled={sending}
              onClick={() => {
                setConversationId(null);
                setMessages([]);
                setLatest(null);
                setProposals([]);
                setSendError(null);
              }}
            >
              New conversation
            </Button>
            <a
              href="#agent-context"
              className="inline-flex min-h-11 items-center rounded-control border border-border px-3 text-sm text-text-secondary hover:bg-surface-2"
            >
              Trade context
            </a>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <Card
          data-testid="agent-history"
          className="order-2 self-start lg:order-1 lg:sticky lg:top-4"
        >
          <CardHeader>
            <CardTitle>History</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {conversations.loading ? (
              <p className="text-caption text-text-muted">Loading…</p>
            ) : null}
            {conversations.error ? (
              <p
                className="text-sm text-danger"
                data-testid="agent-history-error"
              >
                {conversations.error}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => void refreshConversations()}
                >
                  Retry history
                </Button>
              </p>
            ) : null}
            {!conversations.loading &&
            conversations.items.length === 0 &&
            !conversations.error ? (
              <p className="text-sm text-text-muted">No conversations yet.</p>
            ) : null}
            <ul className="max-h-64 space-y-1 overflow-y-auto lg:max-h-[32rem]">
              {conversations.items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={cn(
                      "min-h-11 w-full break-words rounded-control border border-transparent px-3 py-3 text-left text-sm",
                      item.id === conversationId
                        ? "border-accent-border bg-accent-muted text-text-primary"
                        : "text-text-secondary hover:bg-surface-1",
                    )}
                    aria-current={
                      item.id === conversationId ? "true" : undefined
                    }
                    onClick={() => {
                      if (sending || item.id === conversationId) return;
                      setLatest(null);
                      setProposals([]);
                      setSendError(null);
                      setConversationId(item.id);
                    }}
                    disabled={sending}
                  >
                    {item.title?.trim() || "Untitled"}
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <div className="order-1 flex min-w-0 flex-col gap-4 lg:order-2">
          <Card
            data-testid="agent-context"
            id="agent-context"
            className="order-2 scroll-mt-4"
          >
            <CardHeader>
              <CardTitle>Trade context</CardTitle>
              <p className="text-sm text-text-secondary">
                Optional context for your next message.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {positions.loading ? (
                <p role="status" className="text-sm text-text-secondary">
                  Loading open positions…
                </p>
              ) : null}
              {positions.error ? (
                <p className="text-sm text-text-muted">
                  Open positions unavailable
                </p>
              ) : positions.items.length === 0 && !positions.loading ? (
                <p className="text-sm text-text-muted">
                  No open paper positions
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {positions.items.map((position) => (
                    <button
                      key={position.id}
                      type="button"
                      className="min-h-11 break-words rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary hover:bg-surface-2"
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
                    disabled={strategies.loading || Boolean(strategies.error)}
                  >
                    <option value="">
                      {strategies.loading
                        ? "Loading strategies…"
                        : "No strategy selected"}
                    </option>
                    {strategies.items.map((strategy) => (
                      <option key={strategy.id} value={strategy.id}>
                        {strategy.name}
                      </option>
                    ))}
                  </Select>
                  {strategies.error ? (
                    <p className="mt-1 text-caption text-text-muted">
                      Strategies unavailable
                    </p>
                  ) : null}
                </div>
              </div>
              {symbol.trim() ? (
                <p
                  className="text-caption text-text-muted"
                  data-testid="agent-market-context"
                >
                  Market evidence: {marketLabel ?? "…"}
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card className="order-1 border-border">
            <CardHeader className="border-b border-border-subtle">
              <CardTitle>
                {conversations.items
                  .find((item) => item.id === conversationId)
                  ?.title?.trim() || "Conversation"}
              </CardTitle>
              <p className="text-xs text-text-secondary">
                Proposals require your explicit Confirm or Reject.
              </p>
            </CardHeader>
            <CardContent className="space-y-4 pt-4 lg:pt-6">
              {messagesError ? (
                <div
                  role="alert"
                  className="rounded-control border border-danger-border bg-danger-muted p-3 text-sm text-danger"
                >
                  <p>Conversation unavailable: {messagesError}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => setMessagesRetry((value) => value + 1)}
                  >
                    Retry conversation
                  </Button>
                </div>
              ) : null}
              <div
                ref={threadRef}
                aria-label="Conversation messages"
                aria-busy={messagesLoading}
                className="flex min-h-48 max-h-[50dvh] flex-col gap-4 overflow-y-auto overscroll-contain pr-1 lg:min-h-64 lg:max-h-[32rem]"
                data-testid="agent-thread"
              >
                {messagesLoading ? (
                  <p role="status" className="py-6 text-sm text-text-secondary">
                    Loading conversation…
                  </p>
                ) : messagesError ? null : messages.length === 0 ? (
                  <div className="space-y-4 py-5">
                    <MessageSquare
                      className="h-6 w-6 text-accent"
                      aria-hidden="true"
                    />
                    <div>
                      <h2 className="text-lg font-medium">
                        What are you working through?
                      </h2>
                      <p className="mt-2 max-w-lg text-sm leading-relaxed text-text-secondary">
                        Bring your thesis, invalidation, or post-trade notes.
                        The Agent uses available evidence and keeps unavailable
                        data explicit.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {[
                        "Help me review my paper portfolio.",
                        "Challenge my trade thesis and risk assumptions.",
                        "Help me reflect on my last trade.",
                      ].map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          className="min-h-11 rounded-control border border-border-subtle px-3 py-2 text-left text-sm text-text-secondary hover:bg-surface-2"
                          onClick={() => setDraft(prompt)}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((message) => (
                    <div
                      key={message.id}
                      data-testid="agent-message"
                      data-role={message.role}
                      className={cn(
                        "min-w-0 max-w-[95%] rounded-card border px-4 py-3 text-sm leading-relaxed sm:max-w-[85%]",
                        message.role === "user"
                          ? "ml-auto border-border bg-surface-2 text-text-primary"
                          : "mr-auto border-border-subtle bg-surface-0 text-text-secondary",
                      )}
                    >
                      <p className="mb-2 text-xs font-medium text-text-secondary">
                        {messageLabel(message.role)} ·{" "}
                        {formatDateTime(message.created_at)}
                      </p>
                      <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                        {message.content}
                      </p>
                    </div>
                  ))
                )}
              </div>

              {sending ? (
                <p
                  role="status"
                  className="rounded-control border border-border-subtle bg-surface-0/40 p-3 text-sm text-text-secondary"
                >
                  Agent is reviewing your message…
                </p>
              ) : null}
              {proposals.length > 0 ? (
                <ul className="space-y-2" data-testid="agent-proposals">
                  {proposals.map((proposal) => (
                    <li
                      key={proposal.proposal_id}
                      className="rounded-control border border-warning-border bg-warning-muted/30 p-4"
                      data-proposal-status={proposal.status}
                    >
                      <p className="text-sm text-text-primary">
                        {proposal.summary}
                      </p>
                      <p className="text-caption text-text-muted">
                        Status {proposal.status}. The reply did not confirm this
                        proposal.
                      </p>
                      {proposal.kind === "propose_strategy" ? (
                        <p className="text-caption text-text-muted">
                          Confirm records the request only. The strategy preview
                          stays a draft.
                        </p>
                      ) : null}
                      {proposal.kind === "propose_journal_entry" ? (
                        <p className="text-caption text-text-muted">
                          Confirm writes one journal entry. Sending a message
                          does not.
                        </p>
                      ) : null}
                      {proposal.status === "proposed" ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          <Button
                            type="button"
                            onClick={() =>
                              void decideProposal(proposal, "I confirm")
                            }
                            disabled={decidingId !== null}
                          >
                            Confirm proposal
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() =>
                              void decideProposal(proposal, "I reject")
                            }
                            disabled={decidingId !== null}
                          >
                            Reject proposal
                          </Button>
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
              {latest?.market_quote ? (
                <p
                  className="text-caption text-text-muted"
                  data-testid="agent-turn-market"
                >
                  {latest.market_quote.symbol} source{" "}
                  {latest.market_quote.source} live{" "}
                  {String(latest.market_quote.is_live)} stale{" "}
                  {String(latest.market_quote.is_stale)}
                </p>
              ) : null}

              <form
                className="space-y-3 border-t border-border-subtle pt-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void sendMessage();
                }}
              >
                <Textarea
                  aria-label="Message"
                  className="min-h-28 resize-y"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Ask about a paper trade, a rule, or a journal note."
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="submit"
                    disabled={
                      sending ||
                      messagesLoading ||
                      Boolean(messagesError) ||
                      killSwitchActive ||
                      !draft.trim()
                    }
                  >
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
                <p className="text-xs text-text-secondary">
                  Text conversation · screenshots and voice unavailable.
                </p>
                <p
                  id="agent-attachment-contract"
                  className="text-caption text-text-muted"
                >
                  Screenshot analysis is not available. No image is uploaded or
                  interpreted.
                </p>
                <p
                  id="agent-voice-contract"
                  className="text-caption text-text-muted"
                >
                  Voice is not available. No audio is transcribed or played.
                </p>
                {killSwitchActive ? (
                  <p className="text-sm text-danger">
                    Kill switch is active. New messages are paused.
                  </p>
                ) : null}
                {sendError ? (
                  <p
                    role="alert"
                    className="rounded-control border border-danger-border bg-danger-muted p-3 text-sm text-danger"
                  >
                    {sendError} Your message draft is kept until a successful
                    send.
                  </p>
                ) : null}
              </form>
            </CardContent>
          </Card>
        </div>
      </div>

      <details
        className="rounded-card border border-border-subtle p-4"
        data-testid="agent-capability-boundary"
      >
        <summary className="cursor-pointer text-sm font-medium text-text-secondary">
          What this workspace can do
        </summary>
        <div className="mt-4 grid gap-6 lg:grid-cols-2">
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
        </div>
      </details>
    </div>
  );
}
