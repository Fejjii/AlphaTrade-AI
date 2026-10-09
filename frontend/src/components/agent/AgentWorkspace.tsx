"use client";

import { useFocusTrap } from "@/hooks/useFocusTrap";
import { FileUp, Send } from "lucide-react";
import { SavedReceipt } from "@/components/agent/SavedReceipt";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AgentMessageContent } from "./AgentMessageContent";
import { AgentVoiceControls } from "@/components/agent/AgentVoiceControls";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { formatDateTime } from "@/lib/format";
import { api } from "@/lib/api";
import type {
  AgentStructuredProposal,
  AgentTurnResult,
  ConversationMessageRecord,
  ConversationSummary,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

type LoadState<T> = {
  items: T[];
  error: string | null;
  loading: boolean;
};

const emptyLoad = { items: [], error: null, loading: true };
export const AGENT_TURN_TIMEOUT_MS = 180_000;

function messageLabel(role: ConversationMessageRecord["role"]): string {
  if (role === "user") return "You";
  if (role === "assistant") return "Agent";
  return "System";
}

function visibleReply(reply: string | null): string | null {
  return (
    reply?.split("\n\nRecorded facts (not a confirmation):\n", 1)[0] ?? null
  );
}

export function AgentWorkspace() {
  const params = useSearchParams();
  const historyRef = useRef<HTMLDivElement>(null);
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(max-width: 1023px)");
    const update = () => setMobile(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const [historyOpen, setHistoryOpen] = useState(false);
  const closeHistory = useCallback(() => setHistoryOpen(false), []);
  useFocusTrap(historyRef, historyOpen && mobile, closeHistory);
  const [attached, setAttached] = useState<File | null>(null);
  const [attachmentPreview, setAttachmentPreview] = useState<Awaited<
    ReturnType<typeof api.knowledge.previewFile>
  > | null>(null);
  const [sourceDocumentId, setSourceDocumentId] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);
  const sendInFlight = useRef(false);
  const turnAbort = useRef<AbortController | null>(null);
  const turnConversation = useRef<string | null>(null);
  const [voiceContextKey, setVoiceContextKey] = useState(0);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesRetry, setMessagesRetry] = useState(0);
  const [conversations, setConversations] =
    useState<LoadState<ConversationSummary>>(emptyLoad);
  const [conversationId, setConversationId] = useState<string | null>(
    params.get("conversation"),
  );
  const [messages, setMessages] = useState<ConversationMessageRecord[]>([]);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [latest, setLatest] = useState<AgentTurnResult | null>(null);
  const [proposals, setProposals] = useState<AgentStructuredProposal[]>([]);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  useEffect(() => () => turnAbort.current?.abort(), []);

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
  }, [refreshConversations]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setMessagesError(null);
      setMessagesLoading(false);
      return;
    }
    // The turn loads its own messages; avoid a competing history read on creation.
    if (turnConversation.current === conversationId) {
      turnConversation.current = null;
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

  async function sendMessage(
    message = draft,
    source: "text" | "voice" = "text",
  ): Promise<boolean> {
    const text =
      message.trim() || (attached ? "Please organize this document." : "");
    if (!text || sendInFlight.current || messagesLoading || messagesError)
      return false;
    sendInFlight.current = true;
    const controller = new AbortController();
    turnAbort.current = controller;
    const timeout = setTimeout(() => controller.abort(), AGENT_TURN_TIMEOUT_MS);
    setSending(true);
    setSendError(null);
    try {
      let documentId = sourceDocumentId;
      if (attached && !documentId) {
        if (!attachmentPreview)
          throw new Error("Preview the attachment before sending.");
        const imported = await api.knowledge.importFile(
          attached,
          attached.name.replace(/\.[^.]+$/, ""),
          "general_note",
          attachmentPreview.preview_receipt,
        );
        documentId = imported.document_id;
        setSourceDocumentId(documentId);
      }
      const result = await api.agent.turn(
        {
          message: text,
          conversation_id: conversationId ?? undefined,
          source_document_id: documentId ?? undefined,
        },
        { signal: controller.signal },
      );
      setAttached(null);
      setAttachmentPreview(null);
      setSourceDocumentId(null);
      setLatest(result);
      setProposals(result.proposals);
      if (conversationId !== result.conversation_id)
        turnConversation.current = result.conversation_id;
      setConversationId(result.conversation_id);
      if (source === "text")
        setDraft((current) => (current.trim() === text ? "" : current));
      try {
        const page = await api.conversations.listMessages(
          result.conversation_id,
          { limit: 100 },
          { signal: controller.signal },
        );
        setMessages(page.items);
        setMessagesError(null);
      } catch {
        const localTurnId = crypto.randomUUID();
        setMessages((current) => [
          ...current,
          {
            id: `local-user-${localTurnId}`,
            conversation_id: result.conversation_id,
            organization_id: "",
            user_id: "",
            role: "user",
            content: text,
            created_at: new Date().toISOString(),
          },
          {
            id: `local-agent-${localTurnId}`,
            conversation_id: result.conversation_id,
            organization_id: "",
            user_id: "",
            role: "assistant",
            content: result.reply,
            payload: {
              interactive_agent: {
                recorded_evidence: result.recorded_evidence,
                full_reply: result.full_reply,
                sources: result.connections,
              },
            },
            created_at: new Date().toISOString(),
          },
        ]);
      }
      void refreshConversations();
      return true;
    } catch (error) {
      setSendError(
        controller.signal.aborted
          ? "Agent response timed out. The request may have completed; check conversation history before resending."
          : error instanceof Error
            ? error.message
            : "Message failed",
      );
      return false;
    } finally {
      clearTimeout(timeout);
      turnAbort.current = null;
      sendInFlight.current = false;
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

  return (
    <div
      className="space-y-4 [&_input]:text-base [&_select]:text-base [&_textarea]:text-base lg:[&_input]:text-sm lg:[&_select]:text-sm lg:[&_textarea]:text-sm"
      data-testid="agent-workspace"
    >
      <h1 className="sr-only">Agent</h1>
      <div className="flex flex-wrap gap-2" aria-label="Conversation controls">
        <Button
          type="button"
          variant="secondary"
          className="min-h-11"
          disabled={sending}
          onClick={() => {
            setVoiceContextKey((value) => value + 1);
            setConversationId(null);
            setMessages([]);
            setLatest(null);
            setProposals([]);
            setSendError(null);
            setAttached(null);
            setAttachmentPreview(null);
            setSourceDocumentId(null);
          }}
        >
          New conversation
        </Button>
        <Button
          variant="outline"
          aria-expanded={historyOpen}
          onClick={() => setHistoryOpen((v) => !v)}
        >
          History
        </Button>
      </div>

      <div
        className={
          historyOpen
            ? "grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]"
            : "grid gap-4"
        }
      >
        {historyOpen && (
          <>
            <button
              className="fixed inset-0 z-50 bg-black/60 lg:hidden"
              aria-label="Close history"
              onClick={() => setHistoryOpen(false)}
            />
            <div
              ref={historyRef}
              role={mobile ? "dialog" : "complementary"}
              aria-modal={mobile ? true : undefined}
              aria-label="Conversation history"
              data-testid="agent-history"
              className="fixed inset-y-0 left-0 z-[60] w-[min(20rem,calc(100vw-2rem))] overflow-y-auto rounded-none bg-surface-0 lg:relative lg:inset-auto lg:z-auto lg:w-auto lg:self-start lg:rounded-card"
            >
              <CardHeader>
                <CardTitle>History</CardTitle>
                <Button variant="ghost" onClick={() => setHistoryOpen(false)}>
                  Close history
                </Button>
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
                  <p className="text-sm text-text-muted">
                    No conversations yet.
                  </p>
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
                          setVoiceContextKey((value) => value + 1);
                          setLatest(null);
                          setProposals([]);
                          setSendError(null);
                          setConversationId(item.id);
                          setHistoryOpen(false);
                        }}
                        disabled={sending}
                      >
                        {item.title?.trim() || "Untitled"}
                      </button>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </div>
          </>
        )}

        <div className="order-1 flex min-w-0 flex-col gap-4 lg:order-2">
          <Card className="order-1 border-border">
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
                  <p className="py-4 text-sm text-text-muted">
                    Start a conversation.
                  </p>
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
                      <AgentMessageContent message={message} />
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
              {messages
                .filter((m) => m.role === "assistant")
                .map((message) => {
                  const payload = message.payload?.interactive_agent as
                    Record<string, unknown> | undefined;
                  const capture = payload?.capture as
                    Parameters<typeof SavedReceipt>[0]["capture"] | undefined;
                  return capture ? (
                    <SavedReceipt
                      key={`receipt:${message.id}`}
                      capture={capture}
                      conversationId={conversationId!}
                    />
                  ) : null;
                })}
              {latest &&
                !messages.some(
                  (m) =>
                    m.id === latest.assistant_message_id &&
                    (
                      m.payload?.interactive_agent as
                        Record<string, unknown> | undefined
                    )?.capture,
                ) && (
                  <SavedReceipt
                    conversationId={latest.conversation_id}
                    capture={{
                      saved_entries: latest.saved_entries ?? [],
                      status: latest.capture_status ?? "not_needed",
                      error: latest.capture_error,
                      clarification: latest.capture_clarification,
                      source_message_id: latest.capture_source_message_id,
                    }}
                  />
                )}
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
                      (!draft.trim() && !attached) ||
                      (Boolean(attached) && !attachmentPreview)
                    }
                  >
                    <Send className="h-4 w-4" aria-hidden="true" />
                    {sending ? "Sending…" : "Send"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    aria-expanded={importOpen}
                    aria-controls="agent-document-import"
                    onClick={() => setImportOpen((open) => !open)}
                  >
                    <FileUp className="h-4 w-4" aria-hidden="true" />
                    {importOpen ? "Close attachment" : "Attach document"}
                  </Button>
                </div>
                <AgentVoiceControls
                  disabled={
                    sending || messagesLoading || Boolean(messagesError)
                  }
                  conversationKey={String(voiceContextKey)}
                  reply={visibleReply(
                    latest?.reply ??
                      [...messages]
                        .reverse()
                        .find((message) => message.role === "assistant")
                        ?.content ??
                      null,
                  )}
                  compact
                  transcriptActionLabel="Use transcript"
                  onSend={async (transcript) => {
                    setDraft(transcript);
                    return true;
                  }}
                />
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
              {importOpen && (
                <section
                  id="agent-document-import"
                  className="space-y-3 border-t border-border-subtle pt-3"
                  aria-label="Attachment"
                >
                  <Input
                    aria-label="Attach document"
                    type="file"
                    accept=".txt,.md,.docx,.pdf"
                    disabled={sending || previewBusy}
                    onChange={(event) => {
                      setAttached(event.target.files?.[0] ?? null);
                      setAttachmentPreview(null);
                      setSourceDocumentId(null);
                    }}
                  />
                  {attached && (
                    <>
                      <p className="text-sm">{attached.name}</p>
                      <Button
                        type="button"
                        variant="outline"
                        disabled={sending || previewBusy}
                        onClick={async () => {
                          setPreviewBusy(true);
                          setSendError(null);
                          try {
                            setAttachmentPreview(
                              await api.knowledge.previewFile(
                                attached,
                                attached.name.replace(/\.[^.]+$/, ""),
                                "general_note",
                              ),
                            );
                          } catch (error) {
                            setSendError(
                              error instanceof Error
                                ? error.message
                                : "Attachment preview failed",
                            );
                          } finally {
                            setPreviewBusy(false);
                          }
                        }}
                      >
                        Preview attachment
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={sending}
                        onClick={() => {
                          setAttached(null);
                          setAttachmentPreview(null);
                          setSourceDocumentId(null);
                        }}
                      >
                        Remove attachment
                      </Button>
                    </>
                  )}
                  {attachmentPreview && (
                    <details open>
                      <summary className="text-sm">
                        Review extracted content
                      </summary>
                      <Textarea
                        aria-label="Attachment preview"
                        readOnly
                        value={attachmentPreview.extracted_text}
                        rows={8}
                      />
                      {attachmentPreview.warnings.map((w) => (
                        <p key={w} className="text-sm text-warning">
                          {w}
                        </p>
                      ))}
                    </details>
                  )}
                </section>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
