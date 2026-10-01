/**
 * Agent workspace capability boundary.
 *
 * Wired items call the interactive agent turn and proposal endpoints.
 * The conversational reply comes from the existing model and is not confirmation.
 * Missing items stay unavailable. The product must not pretend they work.
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
      "Discuss a trade in text. Replies do not confirm proposals or write trading records.",
  },
  {
    id: "history",
    label: "Conversation history",
    status: "wired",
    contract: "Return to saved conversations and their messages.",
  },
  {
    id: "trade-context",
    label: "Symbol, timeframe, and strategy context",
    status: "wired",
    contract:
      "Set a symbol, timeframe, and strategy for your next message, or select an open position.",
  },
  {
    id: "response-fields",
    label: "Reply and structured proposals",
    status: "wired",
    contract:
      "The turn returns a model reply and zero or more proposals. Confirm and reject are separate requests.",
  },
  {
    id: "strategy-capture",
    label: "Strategy capture",
    status: "wired",
    contract:
      "Confirm records your strategy request. The preview stays a draft and the strategy version stays unchanged.",
  },
  {
    id: "rule-capture",
    label: "Rule capture",
    status: "wired",
    contract:
      "A rule proposal stays unapplied after confirm. Structured rules are not written.",
  },
  {
    id: "journaling",
    label: "Journaling",
    status: "wired",
    contract:
      "Confirm a complete journal proposal to save one entry. Sending a message does not save it.",
  },
  {
    id: "knowledge",
    label: "Knowledge retrieval",
    status: "wired",
    contract:
      "Knowledge matches are read during the turn. There is no separate retrieval button.",
  },
  {
    id: "portfolio-questions",
    label: "Portfolio and market questions",
    status: "wired",
    contract:
      "Market answers use canonical perpetual evidence. Unavailable and stale stay labeled. No price is invented.",
  },
  {
    id: "trade-discussion",
    label: "Trade discussion",
    status: "wired",
    contract: "Discussion is the text turn. It does not place a paper order.",
  },
  {
    id: "pre-trade",
    label: "Pre-trade reasoning",
    status: "wired",
    contract:
      "A selected strategy can be discussed. The turn does not submit an order.",
  },
  {
    id: "reflection",
    label: "Post-trade reflection",
    status: "wired",
    contract:
      "A lesson proposal is not accepted by the reply. Confirm leaves it unapplied.",
  },
  {
    id: "image",
    label: "Image and screenshot attachment",
    status: "missing",
    contract:
      "Screenshot analysis is not implemented. No image is uploaded or interpreted.",
  },
  {
    id: "voice",
    label: "Voice interaction",
    status: "wired",
    contract:
      "Supported browsers transcribe your speech. Review and send it through the same Agent conversation. Reply playback is optional. Proposals still need explicit confirmation.",
  },
  {
    id: "refinement",
    label: "Strategy refinement",
    status: "missing",
    contract:
      "Version edits stay in Strategy Lab. This workspace does not apply refinements.",
  },
] as const;

export function missingAgentCapabilities(): readonly AgentCapability[] {
  return AGENT_CAPABILITIES.filter((item) => item.status === "missing");
}

export function wiredAgentCapabilities(): readonly AgentCapability[] {
  return AGENT_CAPABILITIES.filter((item) => item.status === "wired");
}
