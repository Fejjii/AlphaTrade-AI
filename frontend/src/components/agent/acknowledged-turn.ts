import type { AgentStructuredProposal, AgentTurnResult, ConversationMessageRecord } from "@/lib/api/types";
import { confirmProposalResponse } from "@/lib/api/generated/validators";

function metadata(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function preserveMetadata(local: unknown, fetched: unknown) {
  const previous = metadata(local);
  const next = metadata(fetched);
  const merged: Record<string, unknown> = { ...previous, ...Object.fromEntries(Object.entries(next).filter(([key, value]) =>
    value != null && !(Array.isArray(value) && value.length === 0 && Array.isArray(previous[key])))),
    ...(previous.capture || next.capture ? { capture: preserveMetadata(previous.capture, next.capture) } : {}),
  };
  for (const key of ["full_reply", "recorded_evidence"]) {
    if (typeof previous[key] === "string" && typeof merged[key] === "string" && previous[key].length > merged[key].length)
      merged[key] = previous[key];
  }
  if (Array.isArray(previous.proposals) || Array.isArray(next.proposals)) {
    merged.proposals = mergeProposals(
      Array.isArray(previous.proposals) ? previous.proposals.filter((value): value is AgentStructuredProposal => confirmProposalResponse(value)) : [],
      Array.isArray(next.proposals) ? next.proposals.filter((value): value is AgentStructuredProposal => confirmProposalResponse(value)) : [],
    );
  }
  return merged;
}

export function mergeProposals(previous: AgentStructuredProposal[], next: AgentStructuredProposal[]) {
  const byId = new Map(previous.map(proposal => [proposal.proposal_id, proposal]));
  for (const proposal of next) {
    const local = byId.get(proposal.proposal_id);
    // A stale history snapshot cannot undo an acknowledged decision.
    if (!local || local.status === "proposed" || proposal.status !== "proposed") byId.set(proposal.proposal_id, proposal);
  }
  return [...byId.values()];
}

export function proposalsFromMessages(messages: ConversationMessageRecord[]): AgentStructuredProposal[] {
  return messages.reduce<AgentStructuredProposal[]>((all, message) => {
    const values = metadata(message.payload?.interactive_agent).proposals;
    return Array.isArray(values) ? mergeProposals(all, values.filter((value): value is AgentStructuredProposal => confirmProposalResponse(value))) : all;
  }, []);
}

/** Backend IDs are the only deduplication identity; content may legitimately repeat. */
export function reconcileMessages(
  history: ConversationMessageRecord[],
  retained: ConversationMessageRecord[],
): ConversationMessageRecord[] {
  const byId = new Map(history.map((message) => [message.id, message]));
  for (const message of retained) {
    const fetched = byId.get(message.id);
    byId.set(message.id, fetched ? {
      ...message, ...fetched,
      content: fetched.content.length >= message.content.length ? fetched.content : message.content,
      payload: {
        ...message.payload, ...fetched.payload,
        interactive_agent: preserveMetadata(message.payload?.interactive_agent, fetched.payload?.interactive_agent),
      },
    } : message);
  }
  return [...byId.values()];
}

export function acknowledgedMessages(
  text: string, result: AgentTurnResult,
): ConversationMessageRecord[] {
  const common = {
    conversation_id: result.conversation_id,
    organization_id: "", user_id: "", created_at: new Date().toISOString(),
  };
  return [
    { ...common, id: result.user_message_id, role: "user", content: text },
    { ...common, id: result.assistant_message_id, role: "assistant", content: result.reply,
      payload: { interactive_agent: {
        recorded_evidence: result.recorded_evidence ?? result.reply.split("\n\nRecorded facts (not a confirmation):\n")[1],
        full_reply: result.full_reply,
        sources: result.connections, model_usage: result.model_usage,
        proposals: result.proposals,
        capture: { saved_entries: result.saved_entries ?? [], status: result.capture_status ?? "not_needed",
          error: result.capture_error, clarification: result.capture_clarification,
          source_message_id: result.capture_source_message_id },
      } },
    },
  ];
}
