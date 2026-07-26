import { describe, expect, it } from "vitest";

import {
  hasPrefillContext,
  journalEntryHref,
  parseJournalQuery,
  relatedPlanHref,
  relatedValidationHref,
} from "./journalContext";

describe("journalContext", () => {
  it("parses typed journal query parameters", () => {
    const params = new URLSearchParams({
      proposal_id: "prop-1",
      position_id: "pos-1",
      entry: "entry-1",
      trade_id: "trade-1",
      session_id: "sess-1",
    });
    expect(parseJournalQuery(params)).toEqual({
      proposalId: "prop-1",
      positionId: "pos-1",
      entryId: "entry-1",
      tradeId: "trade-1",
      sessionId: "sess-1",
    });
  });

  it("accepts run_session_id as validation context", () => {
    const params = new URLSearchParams({ run_session_id: "sess-2" });
    expect(parseJournalQuery(params).sessionId).toBe("sess-2");
  });

  it("builds honest related hrefs without inventing relationships", () => {
    expect(hasPrefillContext({ proposalId: "p", positionId: null, entryId: null, tradeId: null, sessionId: null })).toBe(
      true,
    );
    expect(journalEntryHref("abc")).toBe("/journal?entry=abc");
    expect(relatedPlanHref("prop-1")).toBe("/proposals?id=prop-1");
    expect(relatedValidationHref("sess-1")).toBe("/paper-validation/run-sessions/sess-1");
  });
});
