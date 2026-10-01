export type VoiceInputState =
  "idle" | "requesting" | "listening" | "transcribing";

export type VoiceErrorCode =
  | "unsupported"
  | "permission"
  | "unavailable"
  | "network"
  | "no-speech"
  | "timeout"
  | "failed";

export type VoiceError = { code: VoiceErrorCode; message: string };
export type VoiceSession = { stop(): void; cancel(): void };

/** Transport only: providers never know about Agent APIs, tools, or authority. */
export interface VoiceProvider {
  readonly capabilities: { input: boolean; output: boolean };
  listen(callbacks: {
    onState(state: Exclude<VoiceInputState, "idle">): void;
    onTranscript(text: string): void;
    onComplete(text: string): void;
    onError(error: VoiceError): void;
  }): VoiceSession;
  speak(
    text: string,
    callbacks: {
      onStart(): void;
      onEnd(): void;
      onError(error: VoiceError): void;
    },
  ): VoiceSession;
  dispose(): void;
}

export type VoiceProviderFactory = () => VoiceProvider;
