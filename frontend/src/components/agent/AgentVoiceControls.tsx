"use client";

import { Mic, Square, Volume2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { createBrowserVoiceProvider } from "@/lib/voice/browser-voice-provider";
import type {
  VoiceError,
  VoiceInputState,
  VoiceProvider,
  VoiceProviderFactory,
  VoiceSession,
} from "@/lib/voice/types";

export function AgentVoiceControls({
  disabled,
  conversationKey,
  reply,
  onSend,
  createProvider = createBrowserVoiceProvider,
  transcriptActionLabel = "Send transcript",
  compact = false,
}: {
  disabled: boolean;
  conversationKey: string | null;
  reply: string | null;
  onSend(transcript: string): Promise<boolean>;
  createProvider?: VoiceProviderFactory;
  transcriptActionLabel?: string;
  compact?: boolean;
}) {
  const provider = useRef<VoiceProvider | null>(null);
  const inputSession = useRef<VoiceSession | null>(null);
  const diagnosticSession = useRef<VoiceSession | null>(null);
  const sendPending = useRef(false);
  const outputSession = useRef<VoiceSession | null>(null);
  const generation = useRef(0);
  const contextGeneration = useRef(0);
  const speechGeneration = useRef(0);
  const [capabilities, setCapabilities] = useState({
    input: false,
    output: false,
  });
  const [state, setState] = useState<VoiceInputState>("idle");
  const [transcript, setTranscript] = useState("");
  const [ready, setReady] = useState(false);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [speech, setSpeech] = useState<"idle" | "starting" | "speaking">(
    "idle",
  );
  const [error, setError] = useState<VoiceError | null>(null);
  const [diagnostic, setDiagnostic] = useState<"idle" | "checking" | "passed">(
    "idle",
  );
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (state !== "listening" && state !== "requesting") return;
    const started = Date.now();
    setElapsed(0);
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [state]);
  const [canDiagnose, setCanDiagnose] = useState(false);

  const stopSpeech = useCallback(() => {
    speechGeneration.current++;
    outputSession.current?.cancel();
    outputSession.current = null;
    setSpeech("idle");
  }, []);
  const cancelListening = useCallback(() => {
    generation.current++;
    inputSession.current?.cancel();
    inputSession.current = null;
    diagnosticSession.current?.cancel();
    diagnosticSession.current = null;
    setDiagnostic("idle");
    setState("idle");
  }, []);
  const clear = useCallback(() => {
    contextGeneration.current++;
    cancelListening();
    stopSpeech();
    setTranscript("");
    setReady(false);
    setSent(false);
    setError(null);
  }, [cancelListening, stopSpeech]);

  useEffect(() => {
    const instance = createProvider();
    provider.current = instance;
    setCapabilities(instance.capabilities);
    setCanDiagnose(Boolean(instance.diagnoseMicrophone));
    const pause = () => {
      if (document.hidden) {
        cancelListening();
        stopSpeech();
      }
    };
    document.addEventListener("visibilitychange", pause);
    return () => {
      clear();
      instance.dispose();
      provider.current = null;
      document.removeEventListener("visibilitychange", pause);
    };
  }, [createProvider, cancelListening, stopSpeech, clear]);

  useEffect(() => {
    clear();
  }, [conversationKey, clear]);
  useEffect(() => {
    if (disabled) {
      cancelListening();
      stopSpeech();
    }
  }, [disabled, cancelListening, stopSpeech]);
  useEffect(() => {
    stopSpeech();
  }, [reply, stopSpeech]);

  function start() {
    if (
      disabled ||
      sending ||
      diagnostic === "checking" ||
      state !== "idle" ||
      !provider.current
    )
      return;
    clear();
    const token = generation.current;
    inputSession.current = provider.current.listen({
      onState: (next) => {
        if (token === generation.current) setState(next);
      },
      onTranscript: (text) => {
        if (token === generation.current) setTranscript(text);
      },
      onComplete: (text) => {
        if (token !== generation.current) return;
        setState("idle");
        setTranscript(text);
        setReady(Boolean(text.trim()));
      },
      onError: (failure) => {
        if (token !== generation.current) return;
        setState("idle");
        setReady(false);
        setError(failure);
      },
    });
  }

  async function send() {
    if (disabled || sendPending.current || !ready || sent) return;
    sendPending.current = true;
    stopSpeech();
    setSending(true);
    const token = contextGeneration.current;
    try {
      const success = await onSend(transcript);
      if (token === contextGeneration.current && success) {
        setSent(true);
        setReady(false);
      }
    } finally {
      sendPending.current = false;
      setSending(false);
    }
  }

  function diagnoseMicrophone() {
    if (
      disabled ||
      sending ||
      state !== "idle" ||
      diagnostic === "checking" ||
      !provider.current?.diagnoseMicrophone
    )
      return;
    cancelListening();
    stopSpeech();
    setDiagnostic("checking");
    const token = generation.current;
    diagnosticSession.current = provider.current.diagnoseMicrophone({
      onComplete: () => {
        if (token === generation.current) setDiagnostic("passed");
      },
      onError: (failure) => {
        if (token !== generation.current) return;
        setDiagnostic("idle");
        setError(failure);
      },
    });
  }

  function speak() {
    if (
      !reply ||
      disabled ||
      diagnostic === "checking" ||
      state !== "idle" ||
      !provider.current
    )
      return;
    stopSpeech();
    setError(null);
    setSpeech("starting");
    const token = speechGeneration.current;
    outputSession.current = provider.current.speak(reply, {
      onStart: () => {
        if (token === speechGeneration.current) setSpeech("speaking");
      },
      onEnd: () => {
        if (token === speechGeneration.current) setSpeech("idle");
      },
      onError: (failure) => {
        if (token !== speechGeneration.current) return;
        setSpeech("idle");
        setError(failure);
      },
    });
  }

  const active = state !== "idle";
  const status =
    state === "requesting"
      ? "Starting browser speech recognition…"
      : state === "listening"
        ? "Recording · microphone on"
        : state === "transcribing"
          ? "Transcribing…"
          : sent
            ? transcriptActionLabel === "Use transcript"
              ? "Transcript added to message"
              : "Transcript sent"
            : ready
              ? "Transcript ready · review before sending"
              : "Microphone off";

  return (
    <section
      aria-label="Voice controls"
      className={
        compact
          ? "min-w-0 space-y-2"
          : "min-w-0 space-y-3 rounded-control border border-border-subtle p-3"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={active ? "warning" : "outline"}
          className="min-h-11"
          data-testid="agent-voice"
          disabled={
            disabled ||
            sending ||
            diagnostic === "checking" ||
            !capabilities.input ||
            state === "transcribing"
          }
          onClick={active ? () => inputSession.current?.stop() : start}
        >
          {active ? (
            <Square className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Mic className="h-4 w-4" aria-hidden="true" />
          )}
          {active ? "Stop recording" : "Start recording"}
        </Button>
        {!compact || active || transcript || error ? (
          <>
            <Button
              type="button"
              variant="ghost"
              className="min-h-11"
              disabled={
                sending ||
                (!active &&
                  !transcript &&
                  !error &&
                  diagnostic === "idle" &&
                  speech === "idle")
              }
              onClick={clear}
            >
              {active ? "Cancel recording" : "Clear voice"}
            </Button>
          </>
        ) : null}
        {!compact || transcript ? (
          <>
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              disabled={disabled || sending || !ready || sent}
              onClick={() => void send()}
            >
              {transcriptActionLabel}
            </Button>
          </>
        ) : null}
      </div>
      {active || ready || sent ? (
        <p
          role="status"
          aria-live="polite"
          className="text-sm text-text-secondary"
          data-testid="agent-voice-status"
        >
          {status}
          {active
            ? ` · ${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`
            : ""}
        </p>
      ) : null}
      {transcript ? (
        <div className="space-y-1" data-testid="agent-voice-transcript">
          <p className="text-xs font-medium text-text-secondary">
            {ready || sent ? "Transcript" : "Partial transcript · not sent"}
          </p>
          <Textarea
            aria-label="Voice transcript"
            value={transcript}
            disabled={!ready || sent || sending}
            onChange={(event) => setTranscript(event.target.value)}
          />
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error.message}
          {error.sourceCode ? ` (Browser code: ${error.sourceCode})` : ""}
        </p>
      ) : null}
      {canDiagnose && error ? (
        <div className="space-y-2">
          <Button
            type="button"
            variant="outline"
            disabled={
              disabled || sending || active || diagnostic === "checking"
            }
            onClick={diagnoseMicrophone}
          >
            Check microphone capture
          </Button>
          <p role="status" className="text-xs text-text-secondary">
            {diagnostic === "checking"
              ? "Checking microphone capture…"
              : diagnostic === "passed"
                ? "Microphone capture works; all tracks stopped. Speech recognition is a separate browser service."
                : "This check briefly opens the microphone, stops every track immediately, and records or uploads no audio."}
          </p>
        </div>
      ) : null}
      {!capabilities.input ? (
        <p className="text-xs text-text-secondary">
          {compact
            ? "Voice input unavailable. Type your message."
            : "Voice input is unavailable in this browser. Use a supported browser over HTTPS or type your message."}
        </p>
      ) : null}
      {!compact || reply || speech !== "idle" ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="min-h-11"
            disabled={
              disabled ||
              sending ||
              active ||
              diagnostic === "checking" ||
              !reply ||
              !capabilities.output ||
              speech !== "idle"
            }
            onClick={speak}
          >
            <Volume2 className="h-4 w-4" aria-hidden="true" />
            Read Agent reply
          </Button>
          {!compact || speech !== "idle" ? (
            <>
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                disabled={speech === "idle"}
                onClick={stopSpeech}
              >
                Stop speech
              </Button>
            </>
          ) : null}
          {!compact || speech !== "idle" ? (
            <p
              role="status"
              aria-live="polite"
              className="text-sm text-text-secondary"
              data-testid="agent-speech-status"
            >
              {speech === "speaking"
                ? "Speaking"
                : speech === "starting"
                  ? "Starting speech…"
                  : "Speech off"}
            </p>
          ) : null}
        </div>
      ) : null}
      {!capabilities.output ? (
        <p className="text-xs text-text-secondary">
          Speech output is unavailable in this browser. Replies remain available
          as text.
        </p>
      ) : null}
    </section>
  );
}
