import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentVoiceControls } from "./AgentVoiceControls";
import type { VoiceProvider } from "@/lib/voice/types";

let input: Parameters<VoiceProvider["listen"]>[0];
let output: Parameters<VoiceProvider["speak"]>[1];
const cancelInput = vi.fn();
const cancelOutput = vi.fn();
const dispose = vi.fn();
const onSend = vi.fn();
const provider: VoiceProvider = {
  capabilities: { input: true, output: true },
  listen: vi.fn((events) => {
    input = events;
    events.onState("requesting");
    return { stop: () => events.onState("transcribing"), cancel: cancelInput };
  }),
  speak: vi.fn((text, events) => {
    output = events;
    events.onStart();
    return { stop: cancelOutput, cancel: cancelOutput };
  }),
  dispose,
};
const createProvider = () => provider;
const props = {
  disabled: false,
  conversationKey: "c1",
  reply: "Review your recorded risk.",
  onSend,
  createProvider,
};

function record(text = "Review my strategy") {
  fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
  act(() => {
    input.onState("listening");
    input.onTranscript(text);
  });
  fireEvent.click(screen.getByRole("button", { name: "Stop recording" }));
  act(() => input.onComplete(text));
}

describe("Agent voice controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    onSend.mockResolvedValue(true);
  });
  afterEach(cleanup);

  it("shows each listening state and only sends a reviewed final transcript", async () => {
    render(<AgentVoiceControls {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    expect(screen.getByTestId("agent-voice-status")).toHaveTextContent(
      "Starting browser speech recognition",
    );
    act(() => {
      input.onState("listening");
      input.onTranscript("Review my strategy");
    });
    expect(screen.getByTestId("agent-voice-status")).toHaveTextContent(
      "Recording · microphone on",
    );
    expect(
      screen.getByRole("button", { name: "Send transcript" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Stop recording" }));
    expect(screen.getByTestId("agent-voice-status")).toHaveTextContent(
      "Transcribing",
    );
    act(() => input.onComplete("Review my strategy"));
    expect(onSend).not.toHaveBeenCalled();
    await act(async () =>
      fireEvent.click(screen.getByRole("button", { name: "Send transcript" })),
    );
    expect(onSend).toHaveBeenCalledExactlyOnceWith("Review my strategy");
    expect(screen.getByTestId("agent-voice-status")).toHaveTextContent(
      "Transcript sent",
    );
    expect(screen.getByTestId("agent-voice-transcript")).toHaveTextContent(
      "Review my strategy",
    );
    expect(
      screen.getByRole("button", { name: "Send transcript" }),
    ).toBeDisabled();
  });

  it("keeps a failed transcript for retry", async () => {
    onSend.mockResolvedValue(false);
    render(<AgentVoiceControls {...props} />);
    record();
    await act(async () =>
      fireEvent.click(screen.getByRole("button", { name: "Send transcript" })),
    );
    expect(screen.getByTestId("agent-voice-transcript")).toHaveTextContent(
      "Review my strategy",
    );
    expect(
      screen.getByRole("button", { name: "Send transcript" }),
    ).toBeEnabled();
  });

  it("cancels and clears listening, rejecting late callbacks", () => {
    render(<AgentVoiceControls {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    const late = input;
    fireEvent.click(screen.getByRole("button", { name: "Clear voice" }));
    act(() => {
      late.onTranscript("Late speech");
      late.onComplete("Late speech");
    });
    expect(cancelInput).toHaveBeenCalled();
    expect(screen.queryByTestId("agent-voice-transcript")).toBeNull();
    expect(screen.getByTestId("agent-voice-status")).toHaveTextContent(
      "Microphone off",
    );
    expect(onSend).not.toHaveBeenCalled();
  });

  it("handles permission errors and returns to a retryable state", () => {
    render(<AgentVoiceControls {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    act(() =>
      input.onError({
        code: "permission",
        message: "Microphone permission denied",
      }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Microphone permission denied",
    );
    expect(
      screen.getByRole("button", { name: "Start recording" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Send transcript" }),
    ).toBeDisabled();
  });

  it("shows the original safe service error and permits a recording retry", () => {
    render(<AgentVoiceControls {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    act(() =>
      input.onError({
        code: "service",
        sourceCode: "service-not-allowed",
        message: "Speech service rejected access.",
      }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Speech service rejected access. (Browser code: service-not-allowed)",
    );
    record("Recovered recording");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByTestId("agent-voice-transcript")).toHaveTextContent(
      "Recovered recording",
    );
    expect(onSend).not.toHaveBeenCalled();
  });

  it("runs only an explicit microphone check and suppresses late diagnostic results", () => {
    let diagnostic!: {
      onComplete(): void;
      onError(error: import("@/lib/voice/types").VoiceError): void;
    };
    const cancel = vi.fn();
    const diagnoseMicrophone = vi.fn((events) => {
      diagnostic = events;
      return { cancel, stop: cancel };
    });
    const factory = () => ({ ...provider, diagnoseMicrophone });
    render(<AgentVoiceControls {...props} createProvider={factory} />);
    expect(diagnoseMicrophone).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    act(() =>
      input.onError({
        code: "service",
        message: "Speech service rejected access.",
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Check microphone capture" }),
    );
    expect(diagnoseMicrophone).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: "Start recording" }),
    ).toBeDisabled();
    act(() => diagnostic.onComplete());
    expect(
      screen.getByText(/Microphone capture works; all tracks stopped/),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Speech service rejected access.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear voice" }));
    act(() => diagnostic.onComplete());
    expect(cancel).toHaveBeenCalled();
    expect(screen.queryByText(/Microphone capture works/)).toBeNull();
    expect(onSend).not.toHaveBeenCalled();
  });

  it.each(["hidden", "conversation", "disabled", "unmount"])(
    "cancels microphone diagnostics on %s and ignores late results",
    (event) => {
      let complete!: () => void;
      const cancel = vi.fn();
      const factory = () => ({
        ...provider,
        diagnoseMicrophone: (callbacks: { onComplete(): void }) => {
          complete = callbacks.onComplete;
          return { cancel, stop: cancel };
        },
      });
      const view = render(
        <AgentVoiceControls {...props} createProvider={factory} />,
      );
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
      act(() =>
        input.onError({
          code: "service",
          message: "Speech service rejected access.",
        }),
      );
      fireEvent.click(
        screen.getByRole("button", { name: "Check microphone capture" }),
      );
      if (event === "hidden") {
        vi.spyOn(document, "hidden", "get").mockReturnValue(true);
        fireEvent(document, new Event("visibilitychange"));
      }
      if (event === "conversation")
        view.rerender(
          <AgentVoiceControls
            {...props}
            createProvider={factory}
            conversationKey="c2"
          />,
        );
      if (event === "disabled")
        view.rerender(
          <AgentVoiceControls {...props} createProvider={factory} disabled />,
        );
      if (event === "unmount") view.unmount();
      act(() => complete());
      expect(cancel).toHaveBeenCalled();
      expect(screen.queryByText(/Microphone capture works/)).toBeNull();
      expect(onSend).not.toHaveBeenCalled();
      vi.restoreAllMocks();
    },
  );

  it("prevents duplicate sends while the first request is unresolved", async () => {
    let finish!: (value: boolean) => void;
    onSend.mockImplementation(
      () =>
        new Promise<boolean>((resolve) => {
          finish = resolve;
        }),
    );
    render(<AgentVoiceControls {...props} />);
    record();
    const button = screen.getByRole("button", { name: "Send transcript" });
    act(() => {
      fireEvent.click(button);
      fireEvent.click(button);
    });
    expect(onSend).toHaveBeenCalledTimes(1);
    await act(async () => finish(true));
    fireEvent.click(button);
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("plays only on request, stops, and interrupts playback to record", () => {
    render(<AgentVoiceControls {...props} />);
    expect(provider.speak).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Read Agent reply" }));
    expect(provider.speak).toHaveBeenCalledWith(
      props.reply,
      expect.any(Object),
    );
    expect(screen.getByTestId("agent-speech-status")).toHaveTextContent(
      "Speaking",
    );
    fireEvent.click(screen.getByRole("button", { name: "Stop speech" }));
    expect(cancelOutput).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Read Agent reply" }));
    const late = output;
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    act(() => late.onStart());
    expect(cancelOutput).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("agent-speech-status")).toHaveTextContent(
      "Speech off",
    );
  });

  it("clears voice on a conversation change and disposes on unmount", () => {
    const view = render(<AgentVoiceControls {...props} />);
    record();
    fireEvent.click(screen.getByRole("button", { name: "Read Agent reply" }));
    view.rerender(<AgentVoiceControls {...props} conversationKey="c2" />);
    expect(screen.queryByTestId("agent-voice-transcript")).toBeNull();
    expect(screen.getByTestId("agent-speech-status")).toHaveTextContent(
      "Speech off",
    );
    view.unmount();
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("blocks submission while disabled and cancels the microphone", () => {
    const view = render(<AgentVoiceControls {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    const late = input;
    view.rerender(<AgentVoiceControls {...props} disabled />);
    act(() => late.onComplete("Buy now"));
    expect(cancelInput).toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Start recording" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Send transcript" }),
    ).toBeDisabled();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("marks a successful send when the parent disables controls during its request", async () => {
    let finish!: (value: boolean) => void;
    onSend.mockImplementation(
      () =>
        new Promise<boolean>((resolve) => {
          finish = resolve;
        }),
    );
    const view = render(<AgentVoiceControls {...props} />);
    record();
    fireEvent.click(screen.getByRole("button", { name: "Send transcript" }));
    view.rerender(<AgentVoiceControls {...props} disabled />);
    await act(async () => finish(true));
    view.rerender(<AgentVoiceControls {...props} />);
    expect(screen.getByTestId("agent-voice-status")).toHaveTextContent(
      "Transcript sent",
    );
  });

  it("stops recording and playback when the page becomes hidden", () => {
    render(<AgentVoiceControls {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    const lateInput = input;
    vi.spyOn(document, "hidden", "get").mockReturnValue(true);
    fireEvent(document, new Event("visibilitychange"));
    act(() => lateInput.onComplete("Late background transcript"));
    expect(screen.queryByTestId("agent-voice-transcript")).toBeNull();
    expect(cancelInput).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Read Agent reply" }));
    fireEvent(document, new Event("visibilitychange"));
    expect(cancelOutput).toHaveBeenCalled();
    expect(screen.getByTestId("agent-speech-status")).toHaveTextContent(
      "Speech off",
    );
    vi.restoreAllMocks();
  });
});
