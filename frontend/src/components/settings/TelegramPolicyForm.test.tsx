import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { TelegramPolicyForm } from "./TelegramPolicyForm";
import { telegramPolicyFixture as policy } from "./telegram-policy.fixture";

beforeEach(() =>
  vi.spyOn(api.notifications, "updatePreferences").mockResolvedValue({
    telegram_policy: policy,
    telegram_enabled: true,
    in_app_enabled: true,
    webhook_enabled: false,
    min_severity: "info",
  }),
);
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function mount(savedPolicy = policy) {
  const onSaved = vi.fn().mockResolvedValue(undefined);
  render(
    <TelegramPolicyForm policy={savedPolicy} enabled={true} onSaved={onSaved} />,
  );
  return onSaved;
}
function save() {
  fireEvent.click(screen.getByRole("button", { name: "Save Telegram policy" }));
}

describe("Telegram policy V2 full replacement", () => {
  it("preserves SFP lifecycle allowlists while editing shared phase preferences", async () => {
    const savedPolicy = {
      ...policy,
      setup_stages: null,
      event_types: ["SFP_CONFIRMED", "SFP_BLOCKED_BY_RISK"],
    } satisfies typeof policy;
    mount(savedPolicy);
    fireEvent.click(screen.getByLabelText("Forming setup notifications"));
    save();
    await waitFor(() =>
      expect(api.notifications.updatePreferences).toHaveBeenCalledExactlyOnceWith({
        telegram_enabled: true,
        telegram_policy: { ...savedPolicy, forming_alerts: true },
      }),
    );
  });
  it("renders actual saved filters and submits edited fields with unedited filters intact", async () => {
    const onSaved = mount();
    expect(screen.getByLabelText("Watched symbols identifiers")).toHaveValue(
      "BTCUSDT",
    );
    expect(
      screen.getByLabelText("Nested stage filters identifiers"),
    ).toHaveValue("N2, N3");
    expect(screen.getByLabelText("Minimum Telegram severity")).toHaveValue(
      "WATCH",
    );
    expect(screen.getByLabelText("Minimum quality threshold")).toHaveValue(
      null,
    );
    fireEvent.change(screen.getByLabelText("Watched symbols identifiers"), {
      target: { value: "ETHUSDT, BTCUSDT" },
    });
    fireEvent.change(screen.getByLabelText("Cooldown (seconds)"), {
      target: { value: "300" },
    });
    fireEvent.click(screen.getByLabelText("Forming setup notifications"));
    save();
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(api.notifications.updatePreferences).toHaveBeenCalledExactlyOnceWith(
      {
        telegram_enabled: true,
        telegram_policy: {
          ...policy,
          symbol_subscriptions: ["ETHUSDT", "BTCUSDT"],
          cooldown_seconds: 300,
          forming_alerts: true,
        },
      },
    );
    expect(onSaved).toHaveBeenCalledOnce();
  });
  it("preserves all versus none subscriptions and explicit zero quality", async () => {
    mount();
    fireEvent.change(screen.getByLabelText("Watched symbols"), {
      target: { value: "none" },
    });
    fireEvent.change(screen.getByLabelText("Nested stage filters"), {
      target: { value: "all" },
    });
    fireEvent.change(screen.getByLabelText("Minimum quality threshold"), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByLabelText("Enable Telegram quiet hours"));
    fireEvent.click(
      screen.getByLabelText("Enable Telegram notification policy"),
    );
    save();
    await waitFor(() =>
      expect(api.notifications.updatePreferences).toHaveBeenCalledWith({
        telegram_enabled: false,
        telegram_policy: {
          ...policy,
          symbol_subscriptions: [],
          setup_stages: null,
          minimum_quality: 0,
          quiet_hours: null,
        },
      }),
    );
  });
  it("validates strategy UUIDs and quiet hour boundaries before saving", async () => {
    mount();
    fireEvent.change(screen.getByLabelText("Watched strategies"), {
      target: { value: "selected" },
    });
    fireEvent.change(screen.getByLabelText("Watched strategies identifiers"), {
      target: { value: "strategy name" },
    });
    save();
    await screen.findByText(
      "Watched strategies must use valid strategy UUIDs.",
    );
    fireEvent.change(screen.getByLabelText("Watched strategies identifiers"), {
      target: { value: "11111111-1111-4111-8111-111111111111" },
    });
    fireEvent.change(screen.getByLabelText("Quiet hours end"), {
      target: { value: "22:00" },
    });
    save();
    await screen.findByText("Quiet hours start and end must differ.");
    fireEvent.change(screen.getByLabelText("Quiet hours end"), {
      target: { value: "07:00" },
    });
    fireEvent.change(screen.getByLabelText("Quiet hours timezone"), {
      target: { value: "Unknown/Timezone" },
    });
    save();
    await screen.findByText("Use a valid IANA timezone for quiet hours.");
    expect(api.notifications.updatePreferences).not.toHaveBeenCalled();
  });
  it("retains the draft for retry on API failure without reporting saved", async () => {
    const onSaved = mount();
    vi.mocked(api.notifications.updatePreferences).mockRejectedValueOnce(
      new Error("private backend detail"),
    );
    fireEvent.change(screen.getByLabelText("Minimum Telegram severity"), {
      target: { value: "ACTION" },
    });
    save();
    await screen.findByText(
      "Telegram policy could not be saved. Please try again.",
    );
    expect(screen.getByLabelText("Minimum Telegram severity")).toHaveValue(
      "ACTION",
    );
    expect(onSaved).not.toHaveBeenCalled();
    save();
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
  });
});
