import { beforeEach, expect, it } from "vitest";
import { pendingFor, persistPending, recoveryDetails, removePending } from "./turn-recovery";
const key = "11111111-1111-4111-8111-111111111111";
const conversation = "22222222-2222-4222-8222-222222222222";
beforeEach(() => sessionStorage.clear());
it("retains the original body across reload and conflict attachment until acknowledgment", () => {
  const body = { message: "Original request", action: { name: "strategy.create", arguments: { text: "Original request", setup_type: "sfp" } } };
  persistPending("tenant:user", { key, body, conversationId: null, state: "uncertain", createdAt: "2026-01-01T00:00:00Z" });
  expect(pendingFor("tenant:user", null)?.body).toEqual(body);
  const old = pendingFor("tenant:user", null)!;
  persistPending("tenant:user", { ...old, conversationId: conversation, state: "turn_running" });
  expect(pendingFor("tenant:user", null)?.key).toBe(key);
  expect(pendingFor("tenant:user", conversation)?.body).toEqual(body);
  expect(pendingFor("other:user", null)).toBeNull();
  removePending("tenant:user", key);
  expect(pendingFor("tenant:user", null)).toBeNull();
});
it("requires a generated machine reason and UUID identities for recovery", () => {
  expect(recoveryDetails({ error: { details: { reason: "turn_capture", turn_id: key, conversation_id: conversation } } })).toMatchObject({ reason: "turn_capture" });
  expect(recoveryDetails({ error: { details: { reason: "invented", turn_id: key, conversation_id: conversation } } })).toBeNull();
  expect(recoveryDetails({ error: { details: { reason: "turn_running", turn_id: "invalid", conversation_id: conversation } } })).toBeNull();
});
