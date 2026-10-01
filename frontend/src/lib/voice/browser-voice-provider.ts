import type { VoiceError, VoiceProvider, VoiceSession } from "./types";

// The prefixed Web Speech API is not included in TypeScript's DOM library.
export interface BrowserRecognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onresult:
    | ((event: {
        results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
      }) => void)
    | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechWindow = Window & {
  SpeechRecognition?: new () => BrowserRecognition;
  webkitSpeechRecognition?: new () => BrowserRecognition;
  SpeechSynthesisUtterance?: typeof SpeechSynthesisUtterance;
};

export const VOICE_TIMEOUTS = {
  permission: 12_000,
  recording: 60_000,
  transcription: 8_000,
  speech: 120_000,
};

function recognitionError(code: string): VoiceError {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return {
        code: "permission",
        message:
          "Microphone permission was denied. Allow microphone access in browser settings and try again.",
      };
    case "audio-capture":
      return {
        code: "unavailable",
        message:
          "Microphone unavailable. Check that a microphone is connected and accessible.",
      };
    case "network":
      return {
        code: "network",
        message:
          "Speech recognition could not connect. Check your connection and try again.",
      };
    case "no-speech":
      return {
        code: "no-speech",
        message: "No speech was detected. Try recording again.",
      };
    default:
      return {
        code: "failed",
        message: "Speech recognition failed. Try again or type your message.",
      };
  }
}

/** Browser-managed speech; no provider credentials, audio storage, or Agent calls. */
export function createBrowserVoiceProvider(): VoiceProvider {
  const browser =
    typeof window === "undefined" ? undefined : (window as SpeechWindow);
  const Recognition =
    browser?.SpeechRecognition ?? browser?.webkitSpeechRecognition;
  const synthesis = browser?.speechSynthesis;
  const Utterance = browser?.SpeechSynthesisUtterance;
  const input =
    typeof Recognition === "function" && browser?.isSecureContext !== false;
  const output = Boolean(synthesis && typeof Utterance === "function");
  let cancelInput: (() => void) | undefined;
  let cancelOutput: (() => void) | undefined;

  return {
    capabilities: { input, output },
    listen(callbacks) {
      cancelInput?.();
      cancelOutput?.();
      const noop: VoiceSession = { stop() {}, cancel() {} };
      if (!input || !Recognition) {
        callbacks.onError({
          code: "unsupported",
          message:
            "Voice input is unavailable in this browser. Use a supported browser over HTTPS or type your message.",
        });
        return noop;
      }
      let recognition: BrowserRecognition;
      try {
        recognition = new Recognition();
      } catch {
        callbacks.onError(recognitionError("failed"));
        return noop;
      }
      let active = true;
      let stopping = false;
      let finalText = "";
      let timer: ReturnType<typeof setTimeout>;
      const cleanup = () => {
        active = false;
        clearTimeout(timer);
        recognition.onstart =
          recognition.onend =
          recognition.onerror =
          recognition.onresult =
            null;
      };
      const abort = () => {
        cleanup();
        try {
          recognition.abort();
        } catch {
          /* Already ended. */
        }
      };
      const fail = (error: VoiceError) => {
        if (!active) return;
        abort();
        callbacks.onError(error);
      };
      const deadline = (ms: number, message: string) => {
        clearTimeout(timer);
        timer = setTimeout(() => fail({ code: "timeout", message }), ms);
      };
      const stop = () => {
        if (!active || stopping) return;
        stopping = true;
        callbacks.onState("transcribing");
        deadline(
          VOICE_TIMEOUTS.transcription,
          "Transcription timed out. Nothing was sent. Try recording again.",
        );
        try {
          recognition.stop();
        } catch {
          fail(recognitionError("failed"));
        }
      };
      cancelInput = abort;
      recognition.lang = browser?.navigator.language || "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.onstart = () => {
        if (!active || stopping) return;
        callbacks.onState("listening");
        clearTimeout(timer);
        // At the recording limit, finalize captured speech instead of dropping it.
        timer = setTimeout(stop, VOICE_TIMEOUTS.recording);
      };
      recognition.onresult = (event) => {
        if (!active) return;
        const results = Array.from(event.results);
        finalText = results
          .filter((result) => result.isFinal)
          .map((result) => result[0].transcript.trim())
          .join(" ")
          .trim();
        callbacks.onTranscript(
          results
            .map((result) => result[0].transcript.trim())
            .join(" ")
            .trim(),
        );
      };
      recognition.onerror = (event) => fail(recognitionError(event.error));
      recognition.onend = () => {
        if (!active) return;
        cleanup();
        if (finalText) callbacks.onComplete(finalText);
        else callbacks.onError(recognitionError("no-speech"));
      };
      callbacks.onState("requesting");
      deadline(
        VOICE_TIMEOUTS.permission,
        "Microphone access timed out. Nothing was sent. Check browser permissions and try again.",
      );
      try {
        recognition.start();
      } catch {
        fail(recognitionError("failed"));
      }
      return { stop, cancel: abort };
    },
    speak(text, callbacks) {
      cancelOutput?.();
      const noop: VoiceSession = { stop() {}, cancel() {} };
      if (!output || !synthesis || !browser || !Utterance) {
        callbacks.onError({
          code: "unsupported",
          message:
            "Speech output is unavailable in this browser. The Agent reply is available as text.",
        });
        return noop;
      }
      const utterance = new Utterance(text);
      utterance.lang = browser.navigator.language || "en-US";
      let active = true;
      const cleanup = () => {
        active = false;
        clearTimeout(timer);
        utterance.onstart = utterance.onend = utterance.onerror = null;
      };
      const cancel = () => {
        cleanup();
        synthesis.cancel();
      };
      cancelOutput = cancel;
      const fail = (error: VoiceError) => {
        if (!active) return;
        cancel();
        callbacks.onError(error);
      };
      const timer = setTimeout(
        () =>
          fail({
            code: "timeout",
            message:
              "Speech playback timed out. You can read the full reply in the conversation.",
          }),
        VOICE_TIMEOUTS.speech,
      );
      utterance.onstart = () => {
        if (active) callbacks.onStart();
      };
      utterance.onend = () => {
        if (active) {
          cleanup();
          callbacks.onEnd();
        }
      };
      utterance.onerror = () =>
        fail({
          code: "failed",
          message:
            "Speech playback failed. The Agent reply is available as text.",
        });
      try {
        synthesis.speak(utterance);
      } catch {
        fail({
          code: "failed",
          message:
            "Speech playback failed. The Agent reply is available as text.",
        });
      }
      return { stop: cancel, cancel };
    },
    dispose() {
      cancelInput?.();
      cancelOutput?.();
    },
  };
}
