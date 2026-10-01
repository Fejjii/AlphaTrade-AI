import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createBrowserVoiceProvider,
  VOICE_TIMEOUTS,
  type BrowserRecognition,
} from "./browser-voice-provider";

class Recognition implements BrowserRecognition {
  static instances: Recognition[] = [];
  static failStart = false;
  lang = "";
  continuous = false;
  interimResults = false;
  onstart: BrowserRecognition["onstart"] = null;
  onend: BrowserRecognition["onend"] = null;
  onerror: BrowserRecognition["onerror"] = null;
  onresult: BrowserRecognition["onresult"] = null;
  start = vi.fn(() => {
    if (Recognition.failStart) throw new Error("Unavailable");
  });
  stop = vi.fn();
  abort = vi.fn();
  constructor() {
    Recognition.instances.push(this);
  }
  result(text: string, isFinal = true) {
    this.onresult?.({ results: [{ isFinal, 0: { transcript: text } }] });
  }
}

const callbacks = () => ({
  onState: vi.fn(),
  onTranscript: vi.fn(),
  onComplete: vi.fn(),
  onError: vi.fn(),
});

describe("browser voice transport", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Recognition.instances = [];
    Recognition.failStart = false;
    vi.stubGlobal("SpeechRecognition", Recognition);
    vi.stubGlobal("isSecureContext", true);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reports permission, recording and transcription; completes only final speech at end", () => {
    const events = callbacks();
    const provider = createBrowserVoiceProvider();
    const session = provider.listen(events);
    const recognition = Recognition.instances[0];
    expect(events.onState).toHaveBeenLastCalledWith("requesting");
    recognition.onstart?.();
    expect(events.onState).toHaveBeenLastCalledWith("listening");
    recognition.result("Review risk", false);
    expect(events.onTranscript).toHaveBeenCalledWith("Review risk");
    expect(events.onComplete).not.toHaveBeenCalled();
    session.stop();
    session.stop();
    expect(recognition.stop).toHaveBeenCalledTimes(1);
    expect(events.onState).toHaveBeenLastCalledWith("transcribing");
    recognition.onresult?.({
      results: [
        { isFinal: true, 0: { transcript: " Review risk " } },
        { isFinal: true, 0: { transcript: "and my strategy" } },
        { isFinal: false, 0: { transcript: "unconfirmed words" } },
      ],
    });
    recognition.onend?.();
    expect(events.onComplete).toHaveBeenCalledExactlyOnceWith(
      "Review risk and my strategy",
    );
    expect(vi.getTimerCount()).toBe(0);
    provider.dispose();
  });

  it.each([
    ["not-allowed", "permission"],
    ["service-not-allowed", "permission"],
    ["audio-capture", "unavailable"],
    ["network", "network"],
    ["no-speech", "no-speech"],
    ["aborted", "failed"],
  ])("handles %s and ignores late results", (browserError, code) => {
    const events = callbacks();
    createBrowserVoiceProvider().listen(events);
    const recognition = Recognition.instances[0];
    const late = recognition.onresult;
    recognition.onerror?.({ error: browserError });
    late?.({ results: [{ isFinal: true, 0: { transcript: "Late request" } }] });
    expect(events.onError).toHaveBeenCalledWith(
      expect.objectContaining({ code }),
    );
    expect(recognition.abort).toHaveBeenCalled();
    expect(events.onTranscript).not.toHaveBeenCalled();
    expect(events.onComplete).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("bounds the permission wait and can retry", () => {
    const provider = createBrowserVoiceProvider();
    const events = callbacks();
    provider.listen(events);
    vi.advanceTimersByTime(VOICE_TIMEOUTS.permission);
    expect(events.onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "timeout" }),
    );
    provider.listen(callbacks());
    expect(Recognition.instances).toHaveLength(2);
    provider.dispose();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("finalizes at the recording limit and bounds a stalled transcription", () => {
    const events = callbacks();
    createBrowserVoiceProvider().listen(events);
    Recognition.instances[0].onstart?.();
    vi.advanceTimersByTime(VOICE_TIMEOUTS.recording);
    expect(Recognition.instances[0].stop).toHaveBeenCalledTimes(1);
    expect(events.onState).toHaveBeenLastCalledWith("transcribing");
    vi.advanceTimersByTime(VOICE_TIMEOUTS.transcription);
    expect(events.onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "timeout" }),
    );
    expect(events.onComplete).not.toHaveBeenCalled();
  });

  it("rejects an empty or interim-only transcript", () => {
    const events = callbacks();
    createBrowserVoiceProvider().listen(events);
    Recognition.instances[0].result("interim only", false);
    Recognition.instances[0].onend?.();
    expect(events.onComplete).not.toHaveBeenCalled();
    expect(events.onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "no-speech" }),
    );
  });

  it("cancels recording without completing and ignores delayed callbacks", () => {
    const events = callbacks();
    const session = createBrowserVoiceProvider().listen(events);
    const lateEnd = Recognition.instances[0].onend;
    Recognition.instances[0].result("Do not send this");
    session.cancel();
    lateEnd?.();
    expect(events.onComplete).not.toHaveBeenCalled();
    expect(events.onError).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("supports the prefixed API and reports unsupported or insecure input", () => {
    vi.stubGlobal("SpeechRecognition", undefined);
    vi.stubGlobal("webkitSpeechRecognition", Recognition);
    expect(createBrowserVoiceProvider().capabilities.input).toBe(true);
    vi.stubGlobal("isSecureContext", false);
    const provider = createBrowserVoiceProvider();
    const events = callbacks();
    expect(provider.capabilities.input).toBe(false);
    provider.listen(events);
    expect(events.onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "unsupported" }),
    );
  });

  it("handles a synchronous recognition start failure", () => {
    Recognition.failStart = true;
    const events = callbacks();
    createBrowserVoiceProvider().listen(events);
    expect(events.onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "failed" }),
    );
    expect(Recognition.instances[0].abort).toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("stops speech on interruption and ignores late speech events", () => {
    let spoken: SpeechSynthesisUtterance | undefined;
    class Utterance {
      constructor(public text: string) {}
    }
    const synthesis = {
      speak: vi.fn((value: SpeechSynthesisUtterance) => {
        spoken = value;
      }),
      cancel: vi.fn(),
    };
    vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
    vi.stubGlobal("speechSynthesis", synthesis);
    const provider = createBrowserVoiceProvider();
    const events = { onStart: vi.fn(), onEnd: vi.fn(), onError: vi.fn() };
    expect(provider.capabilities.output).toBe(true);
    const session = provider.speak("Agent reply", events);
    spoken?.onstart?.(new Event("start") as SpeechSynthesisEvent);
    expect(events.onStart).toHaveBeenCalledTimes(1);
    const lateEnd = spoken?.onend;
    session.cancel();
    lateEnd?.call(spoken!, new Event("end") as SpeechSynthesisEvent);
    expect(events.onEnd).not.toHaveBeenCalled();
    provider.speak("Another reply", events);
    provider.listen(callbacks());
    expect(synthesis.cancel).toHaveBeenCalled();
    provider.dispose();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("bounds speech playback and handles missing output independently", () => {
    class Utterance {
      constructor(public text: string) {}
    }
    vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
    vi.stubGlobal("speechSynthesis", { speak: vi.fn(), cancel: vi.fn() });
    const events = { onStart: vi.fn(), onEnd: vi.fn(), onError: vi.fn() };
    createBrowserVoiceProvider().speak("Reply", events);
    vi.advanceTimersByTime(VOICE_TIMEOUTS.speech);
    expect(events.onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "timeout" }),
    );
    vi.stubGlobal("speechSynthesis", undefined);
    const provider = createBrowserVoiceProvider();
    expect(provider.capabilities).toEqual({ input: true, output: false });
    provider.speak("Reply", events);
    expect(events.onError).toHaveBeenLastCalledWith(
      expect.objectContaining({ code: "unsupported" }),
    );
    vi.stubGlobal("speechSynthesis", { speak: vi.fn(), cancel: vi.fn() });
    vi.stubGlobal("SpeechSynthesisUtterance", undefined);
    expect(createBrowserVoiceProvider().capabilities.output).toBe(false);
  });
});
