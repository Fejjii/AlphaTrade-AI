import type { VoiceError, VoiceProvider } from "./types";

export type VoiceConversationState =
  | "idle" | "requesting" | "listening" | "preparing"
  | "waiting" | "speaking" | "paused" | "error";

/** Immutable voice envelope. The integrator owns the complete backend body and recovery store. */
export type VoiceTurn = Readonly<{
  turnKey: string;
  transcript: string;
  conversationId: string;
  origin: "voice";
}>;

export type VoiceTurnResult =
  | { outcome: "acknowledged"; reply: string }
  | { outcome: "rejected" }
  | { outcome: "uncertain" };

/** Route both methods through the existing Agent admission/turn/recovery pipeline. */
export interface VoiceAgentTransport {
  submit(request: VoiceTurn & { signal: AbortSignal }): Promise<VoiceTurnResult>;
  recover(request: VoiceTurn & { signal: AbortSignal }): Promise<VoiceTurnResult>;
  /** Restore a pending voice envelope from the authoritative, user-scoped turn store. */
  pending?(conversationId: string): VoiceTurn | null;
}

export type VoiceConversationSnapshot = Readonly<{
  state: VoiceConversationState;
  sessionActive: boolean;
  mode: "review" | "conversation";
  playback: boolean;
  transcript: string;
  ready: boolean;
  reply: string;
  unresolved: VoiceTurn | null;
  error: { message: string; diagnostic?: VoiceError } | null;
  capabilities: VoiceProvider["capabilities"];
  startedAt: number | null;
}>;

export interface VoiceConversationOptions {
  provider: VoiceProvider;
  transport: VoiceAgentTransport;
  getTypedDraft(): string;
  setTypedDraft(text: string): void;
  createTurnKey?: () => string;
  agentTimeoutMs?: number;
}
