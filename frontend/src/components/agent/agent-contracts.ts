/**
 * Agent workspace capability boundary.
 *
 * Wired items match the existing chat and conversation APIs.
 * Missing items are UI boundaries only — the product must not pretend they work.
 */

export type AgentCapabilityStatus = "wired" | "missing";

export type AgentCapability = {
  id: string;
  label: string;
  status: AgentCapabilityStatus;
  contract: string;
};

export const AGENT_CAPABILITIES: readonly AgentCapability[] = [
  {
    id: "text-chat",
    label: "Text conversation",
    status: "wired",
    contract:
      "POST /chat/message accepts message, and optional conversation_id, strategy_id, symbol, and timeframe.",
  },
  {
    id: "history",
    label: "Conversation history",
    status: "wired",
    contract: "GET/POST /conversations and GET /conversations/{id}/messages.",
  },
  {
    id: "trade-context",
    label: "Symbol, timeframe, and strategy context",
    status: "wired",
    contract:
      "Those fields are sent on ChatMessageRequest. Open positions come from GET /positions.",
  },
  {
    id: "response-fields",
    label: "Reply, citations, risk, and proposal preview",
    status: "wired",
    contract:
      "The latest AgentMessageResponse may include reply, citations, risk_result, and pending_proposal. Confirming a proposal is not offered here.",
  },
  {
    id: "image",
    label: "Image and screenshot attachment",
    status: "missing",
    contract:
      "ChatMessageRequest is text only. There is no image or multipart field, so attachments cannot be sent.",
  },
  {
    id: "voice",
    label: "Voice interaction",
    status: "missing",
    contract: "No voice request field or transcription endpoint exists on the chat API.",
  },
  {
    id: "strategy-capture",
    label: "Strategy capture",
    status: "missing",
    contract:
      "No dedicated strategy-capture action. A pending_proposal may appear on a reply; confirmation requires content hashes and is not a composer action.",
  },
  {
    id: "rule-capture",
    label: "Rule capture",
    status: "missing",
    contract: "No dedicated rule-capture endpoint is exposed to this workspace.",
  },
  {
    id: "trade-discussion",
    label: "Trade discussion",
    status: "missing",
    contract:
      "Discussion is only the text chat message. There is no separate trade-discussion mode.",
  },
  {
    id: "pre-trade",
    label: "Pre-trade reasoning",
    status: "missing",
    contract: "No dedicated pre-trade action. Use the existing Pre-Trade page for that workflow.",
  },
  {
    id: "journaling",
    label: "Journaling",
    status: "missing",
    contract: "The Agent does not write journal entries. Record trades from Journal.",
  },
  {
    id: "reflection",
    label: "Post-trade reflection",
    status: "missing",
    contract: "No stored per-trade Agent reflection record is returned by the journal API.",
  },
  {
    id: "knowledge",
    label: "Knowledge retrieval",
    status: "missing",
    contract:
      "Citations on a reply are shown when the API returns them. There is no separate retrieval action in this workspace.",
  },
  {
    id: "refinement",
    label: "Strategy refinement",
    status: "missing",
    contract: "Version edits stay in Strategy Lab. This workspace does not apply refinements.",
  },
  {
    id: "portfolio-questions",
    label: "Portfolio and statistics questions",
    status: "missing",
    contract:
      "Ask in text if you want. There is no dedicated portfolio-question tool exposed in this workspace, and answers are only the chat reply.",
  },
] as const;

export function missingAgentCapabilities(): readonly AgentCapability[] {
  return AGENT_CAPABILITIES.filter((item) => item.status === "missing");
}

export function wiredAgentCapabilities(): readonly AgentCapability[] {
  return AGENT_CAPABILITIES.filter((item) => item.status === "wired");
}
