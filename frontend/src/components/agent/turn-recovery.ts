import { agentTurnRequest, turnConflictDetails } from "@/lib/api/generated/validators";
import type { components } from "@/lib/api/generated/types";

export type TurnBody = components["schemas"]["AgentTurnRequest"];
export type ConflictDetails = components["schemas"]["TurnConflictDetails"];
export type PendingTurn = {
  key: string;
  body: TurnBody;
  conversationId: string | null;
  state: "uncertain" | ConflictDetails["reason"];
  createdAt: string;
};

const prefix = "alphatrade:pending-turn:";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function read(scope: string): PendingTurn[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(prefix + scope) ?? "[]");
    return Array.isArray(value) ? value.filter((p): p is PendingTurn =>
      p && typeof p === "object" && uuid.test(p.key) && agentTurnRequest(p.body) &&
      typeof p.createdAt === "string" && Number.isFinite(Date.parse(p.createdAt)) &&
      (p.conversationId === null || (typeof p.conversationId === "string" && uuid.test(p.conversationId))) &&
      (p.state === "uncertain" || turnConflictDetails({ reason: p.state, turn_id: p.key,
        conversation_id: p.conversationId ?? "00000000-0000-0000-0000-000000000000" }))) : [];
  } catch { return []; }
}

export function pendingFor(scope: string, conversation: string | null): PendingTurn | null {
  return read(scope).filter(p => p.conversationId === conversation || (conversation === null && !p.body.conversation_id)).at(-1) ?? null;
}

export function persistPending(scope: string, pending: PendingTurn): void {
  try {
    const retained = read(scope).filter(p => p.key !== pending.key);
    sessionStorage.setItem(prefix + scope, JSON.stringify([...retained, pending]));
  } catch { /* In-memory recovery remains available if tab storage is unavailable. */ }
}

export function removePending(scope: string, key: string): void {
  try { sessionStorage.setItem(prefix + scope, JSON.stringify(read(scope).filter(p => p.key !== key))); }
  catch { /* Preserve the active in-memory state. */ }
}

export function clearPendingTurns(): void {
  try {
    Object.keys(sessionStorage).filter(key => key.startsWith(prefix)).forEach(key => sessionStorage.removeItem(key));
  } catch { /* Storage may be unavailable. */ }
}

export function recoveryDetails(body: unknown): ConflictDetails | null {
  const details = (body as { error?: { details?: unknown } } | null)?.error?.details;
  return turnConflictDetails(details) ? details : null;
}
