"use client";

import { Mic, Square, Volume2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { createBrowserVoiceProvider } from "@/lib/voice/browser-voice-provider";
import type {
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
}: {
  disabled: boolean;
  conversationKey: string | null;
  reply: string | null;
  onSend(transcript: string): Promise<boolean>;
  createProvider?: VoiceProviderFactory;
}) {
  const provider = useRef<VoiceProvider | null>(null);
  const inputSession = useRef<VoiceSession | null>(null);
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
  const [error, setError] = useState<string | null>(null);

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
    if (disabled || sending || state !== "idle" || !provider.current) return;
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
        setError(failure.message);
      },
    });
  }

  async function send() {
    if (disabled || sending || !ready || sent) return;
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
      setSending(false);
    }
  }

  function speak() {
    if (!reply || disabled || state !== "idle" || !provider.current) return;
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
        setError(failure.message);
      },
    });
  }

  const active = state !== "idle";
  const status =
    state === "requesting"
      ? "Waiting for microphone permission…"
      : state === "listening"
        ? "Recording · microphone on"
        : state === "transcribing"
          ? "Transcribing…"
          : sent
            ? "Transcript sent"
            : ready
              ? "Transcript ready · review before sending"
              : "Microphone off";

  return (
    <section
      aria-label="Voice controls"
      className="min-w-0 space-y-3 rounded-control border border-border-subtle p-3"
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
        <Button
          type="button"
          variant="ghost"
          className="min-h-11"
          disabled={
            sending || (!active && !transcript && !error && speech === "idle")
          }
          onClick={clear}
        >
          Clear voice
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          disabled={disabled || sending || !ready || sent}
          onClick={() => void send()}
        >
          Send transcript
        </Button>
      </div>
      <p
        role="status"
        aria-live="polite"
        className="text-sm text-text-secondary"
        data-testid="agent-voice-status"
      >
        {status}
      </p>
      {transcript ? (
        <div className="space-y-1" data-testid="agent-voice-transcript">
          <p className="text-xs font-medium text-text-secondary">
            {ready || sent ? "Transcript" : "Partial transcript · not sent"}
          </p>
          <p className="whitespace-pre-wrap break-words text-sm text-text-primary [overflow-wrap:anywhere]">
            {transcript}
          </p>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      {!capabilities.input ? (
        <p className="text-xs text-text-secondary">
          Voice input is unavailable in this browser. Use a supported browser
          over HTTPS or type your message.
        </p>
      ) : (
        <p className="text-xs text-text-secondary">
          Your browser handles microphone access and transcription and may send
          audio to its speech service. Review the transcript, then send it to
          this conversation.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          disabled={
            disabled ||
            sending ||
            active ||
            !reply ||
            !capabilities.output ||
            speech !== "idle"
          }
          onClick={speak}
        >
          <Volume2 className="h-4 w-4" aria-hidden="true" />
          Read Agent reply
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          disabled={speech === "idle"}
          onClick={stopSpeech}
        >
          Stop speech
        </Button>
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
      </div>
      {!capabilities.output ? (
        <p className="text-xs text-text-secondary">
          Speech output is unavailable in this browser. Replies remain available
          as text.
        </p>
      ) : null}
    </section>
  );
}
