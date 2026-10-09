import { describe, expect, it } from "vitest";
import { agentTurnFixture, FIXTURE_UUID } from "@/test/pilot-fixtures";
import { acknowledgedMessages, proposalsFromMessages, reconcileMessages } from "./acknowledged-turn";
import type { AgentStructuredProposal } from "@/lib/api/types";

const proposal: AgentStructuredProposal = {
  proposal_id: FIXTURE_UUID, conversation_id: FIXTURE_UUID, organization_id: FIXTURE_UUID,
  user_id: FIXTURE_UUID, kind: "propose_journal_entry", artifact_kind: "journal_entry",
  authority: "explicit_confirmation", provenance: "user_supplied", status: "applied",
  content_hash: "a".repeat(64), summary: "Acknowledged journal decision", payload: {},
  applied: true, authority_mutated: true,
};

describe("acknowledged turn reconciliation", () => {
  it("deduplicates only exact IDs while retaining repeated text from separate turns", () => {
    const first = acknowledgedMessages("Repeated text", agentTurnFixture);
    const second = acknowledgedMessages("Repeated text", { ...agentTurnFixture,
      user_message_id: "44444444-4444-4444-8444-444444444444",
      assistant_message_id: "55555555-5555-4555-8555-555555555555" });
    expect(reconcileMessages(first, [...first, ...second])).toHaveLength(4);
  });
  it("retains full reply, receipts, evidence and decided proposal through incomplete stale metadata", () => {
    const local = acknowledgedMessages("Record", { ...agentTurnFixture, full_reply: "Full explanation",
      recorded_evidence: "Recorded evidence", proposals: [proposal], saved_entries: [], capture_status: "saved" });
    const stale = local.map(message => ({ ...message, payload: { interactive_agent: {
      full_reply: "Full", recorded_evidence: null, proposals: [{ ...proposal, status: "proposed" }],
      capture: { saved_entries: [], error: null },
    } } }));
    const merged = reconcileMessages(stale, local);
    expect(merged[1].payload?.interactive_agent).toMatchObject({ full_reply: "Full explanation",
      recorded_evidence: "Recorded evidence", capture: { status: "saved" } });
    expect(proposalsFromMessages(merged)).toEqual([proposal]);
  });
  it("does not create actionable proposals from malformed history metadata", () => {
    const messages = acknowledgedMessages("Record", agentTurnFixture);
    messages[1].payload = { interactive_agent: { proposals: [{ ...proposal, authority_mutated: "false" }] } };
    expect(proposalsFromMessages(messages)).toEqual([]);
  });
});
