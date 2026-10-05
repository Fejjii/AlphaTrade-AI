import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "./page";
import { api } from "@/lib/api";
import type {
  HealthResponse,
  ProviderStatusResponse,
  UserRiskSettings,
} from "@/lib/api/types";
import { makeWatcherMonitoringSnapshot } from "@/lib/watcher-monitoring-fixtures";

const runtime = {
  health: null as HealthResponse | null,
  providers: null as ProviderStatusResponse | null,
  loading: false,
  refreshStatus: vi.fn(),
};
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "owner@example.com", email_verified: true },
    organization: { name: "Alpha Org" },
  }),
}));
vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => runtime,
  useSafetyPosture: () => ({
    executionMode: runtime.health?.execution_mode ?? null,
    realTradingEnabled: runtime.health?.real_trading_enabled ?? null,
    postureKnown: runtime.health !== null,
  }),
}));

const risk: UserRiskSettings = {
  organization_id: "org-1",
  user_id: "user-1",
  daily_loss_limit: "75.25",
  daily_target: null,
  max_trades_per_day: 4,
  max_risk_per_trade_percent: "0.75",
  default_account_balance: "10000.00",
  timezone: "Europe/Berlin",
  green_day_protection_enabled: true,
  one_loss_stop_enabled: false,
  overtrading_guard_enabled: true,
  notes: null,
  using_defaults: false,
  timezone_fallback: false,
};
const snapshot = makeWatcherMonitoringSnapshot({
  watcher_status: "STALE",
  paper_monitoring_status: "STOPPED",
  paper_posture: {
    ...makeWatcherMonitoringSnapshot().paper_posture,
    watcher_config_enabled: true,
  },
  approved_strategies: [
    {
      strategy_id: "s1",
      strategy_version_id: "active-v2",
      name: "Breakout",
      lifecycle_state: "active",
      compiled: true,
    },
    {
      strategy_id: "s1",
      strategy_version_id: "approved-v3",
      name: "Breakout",
      lifecycle_state: "approved",
      compiled: true,
    },
  ],
  market_freshness: { status: "replay", observed_at: "2026-10-01T10:00:00Z" },
  scanner_candidates: {
    count: 3,
    conditions: [],
    source: "market_watcher_scan",
  },
});
const slots = [
  { position: 1, symbol: "BTCUSDT", enabled: true },
  { position: 2, symbol: "ETHUSDT", enabled: false },
];

beforeEach(() => {
  vi.restoreAllMocks();
  runtime.health = {
    execution_mode: "paper",
    real_trading_enabled: false,
    telegram_network_permitted: false,
  } as HealthResponse;
  runtime.providers = {
    generated_at: "2026-10-01T10:00:00Z",
    providers: [
      {
        name: "Replay",
        kind: "market_data",
        health: "healthy",
        is_mock: true,
        using_fallback: false,
      },
    ],
  };
  runtime.refreshStatus = vi.fn().mockResolvedValue(undefined);
  vi.spyOn(api.execution, "paperAccountStatus").mockResolvedValue({
    account: null, can_register: true,
  });
  vi.spyOn(api.marketWatcher, "monitoring").mockResolvedValue(snapshot);
  vi.spyOn(api.strategies, "listVersions").mockResolvedValue({
    items: [
      {
        id: "active-v2",
        strategy_id: "s1",
        version: 2,
        card: {},
        validation_status: "approved",
        backtest_status: "passed",
        paper_validation_status: "completed",
        created_at: "2026-10-01T10:00:00Z",
      },
      {
        id: "approved-v3",
        strategy_id: "s1",
        version: 3,
        card: {},
        validation_status: "approved",
        backtest_status: "passed",
        paper_validation_status: "completed",
        created_at: "2026-10-01T10:00:00Z",
      },
    ],
    total: 2,
    limit: 50,
    offset: 0,
  });
  vi.spyOn(api.risk, "settings").mockResolvedValue(risk);
  vi.spyOn(api.risk, "updateSettings").mockRejectedValue(
    new Error("Risk must remain read only"),
  );
  vi.spyOn(api.notifications, "preferences").mockResolvedValue({
    in_app_enabled: true,
    webhook_enabled: false,
    telegram_enabled: false,
    min_severity: "warning",
  });
  vi.spyOn(api.notifications, "updatePreferences").mockResolvedValue({
    in_app_enabled: true,
    webhook_enabled: false,
    telegram_enabled: false,
    min_severity: "critical",
  });
  vi.spyOn(api.notifications, "sendTest").mockRejectedValue(
    new Error("Must not deliver"),
  );
  vi.spyOn(api.alerts, "testTelegram").mockRejectedValue(
    new Error("Must not deliver"),
  );
  vi.spyOn(api.alerts, "deliverPending").mockRejectedValue(
    new Error("Must not deliver"),
  );
  vi.spyOn(api.alerts, "deliveryStatus").mockResolvedValue({
    delivery_enabled: false,
    webhook_enabled: false,
    telegram_enabled: false,
    email_enabled: false,
    push_enabled: false,
    webhook_configured: false,
    effective_external_enabled: false,
    channels: [],
    paper_only: true,
    channel_statuses: [
      {
        channel: "telegram",
        env_enabled: false,
        user_enabled: false,
        configured: true,
        available: false,
        status_label: "disabled",
      },
    ],
  });
  vi.spyOn(api.watcherWatchlist, "configuration").mockResolvedValue({
    revision: 7,
    slots,
    max_enabled: 5,
    paper_only: true,
    updated_at: "2026-10-01T10:00:00Z",
  });
  vi.spyOn(api.watcherWatchlist, "status").mockResolvedValue({
    configuration_revision: 7,
    observed_at: new Date().toISOString(),
    stale_after_seconds: 90,
    paper_only: true,
    real_trading_enabled: false,
    symbols: [],
  });
});

it("sets up only paper identity from the Account settings section and exposes its UUID", async () => {
  const id = "93ef7157-4a5e-4ae1-a660-3ed93b04ed31";
  vi.spyOn(api.execution, "registerPaperAccount").mockResolvedValue({
    account: { id, name: "Paper account", execution_mode: "PAPER", account_mode: "NET", enabled: true },
    created: true,
  });
  render(<SettingsPage />);
  const section = screen.getByRole("region", { name: "Account and system" });
  fireEvent.click(await within(section).findByRole("button", { name: "Set up paper account" }));
  expect(await within(section).findByText(id)).toBeInTheDocument();
  expect(api.execution.registerPaperAccount).toHaveBeenCalledExactlyOnceWith();
  expect(api.risk.updateSettings).not.toHaveBeenCalled();
});
afterEach(cleanup);

async function loaded() {
  render(<SettingsPage />);
  await screen.findByText("Version 2 · Active paper version");
}

describe("Trader Settings workspace", () => {
  it("has the five sections and keeps engineering detail in Advanced", async () => {
    await loaded();
    expect(
      screen
        .getAllByRole("heading", { level: 2 })
        .map((heading) => heading.textContent),
    ).toEqual([
      "Markets",
      "Strategies",
      "Notifications",
      "Risk",
      "Account and system",
    ]);
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    expect(within(nav).getByRole("link", { name: "Risk" })).toHaveAttribute(
      "href",
      "#risk",
    );
    expect(
      screen.getByRole("link", { name: "Advanced settings" }),
    ).toHaveAttribute("href", "/settings/advanced");
    expect(
      screen.getByRole("link", { name: "Billing & Usage" }),
    ).toHaveAttribute("href", "/settings/billing");
    expect(screen.getByTestId("settings-email-verified")).toHaveTextContent(
      "Yes — verified",
    );
    expect(
      screen.queryByTestId("settings-build-config"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", {
        name: /Open Dashboard|Watcher diagnostics/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("shows the saved market enabled state and reported universe without treating enablement as running", async () => {
    await loaded();
    expect(screen.getByLabelText("Enable slot 1")).toBeChecked();
    expect(screen.getByLabelText("Enable slot 2")).not.toBeChecked();
    expect(screen.getByText(/Reported monitoring universe:/)).toHaveTextContent(
      "BTCUSDT, ETHUSDT, SOLUSDT",
    );
    expect(screen.getByTestId("settings-runtime-posture")).toHaveTextContent(
      "stale",
    );
    expect(screen.getByTestId("settings-runtime-posture")).toHaveTextContent(
      "replay",
    );
    expect(screen.getByTestId("settings-provider-health")).toHaveTextContent(
      "Replay: healthy · Simulated",
    );
    expect(
      screen.getByText(/Market data providers/).parentElement,
    ).toHaveTextContent("Replay: healthy (simulated)");
  });

  it("resolves the exact approved version rather than assuming the current strategy version is active", async () => {
    await loaded();
    expect(
      screen.getByText("Version 3 · Approved for monitoring"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("settings-strategies-summary")).toHaveTextContent(
      "stopped",
    );
    expect(screen.getByTestId("settings-strategies-summary")).toHaveTextContent(
      "Setups detected in the last scan: 3",
    );
    expect(api.strategies.listVersions).toHaveBeenCalledTimes(1);
    expect(api.strategies.listVersions).toHaveBeenCalledWith("s1");
  });

  it("keeps version references and lifecycle visible when numeric version lookup fails", async () => {
    vi.mocked(api.strategies.listVersions).mockRejectedValue(
      new Error("Unavailable"),
    );
    render(<SettingsPage />);
    await screen.findByText(
      "Version number unavailable · Active paper version",
    );
    expect(screen.getByText("active-v2")).toBeInTheDocument();
    expect(screen.getByTestId("settings-strategies-summary")).toHaveTextContent(
      "stopped",
    );
  });

  it("displays canonical risk settings including explicit zero and unset values without risk inputs", async () => {
    vi.mocked(api.risk.settings).mockResolvedValue({
      ...risk,
      daily_loss_limit: "0",
      using_defaults: true,
    });
    await loaded();
    const card = screen.getByTestId("settings-risk-summary");
    expect(card).toHaveTextContent("Maximum risk per trade0.75%");
    expect(
      within(card).getByText("Daily loss limit").parentElement,
    ).toHaveTextContent("0");
    expect(
      within(card).getByText("Daily profit target").parentElement,
    ).toHaveTextContent("Not set");
    expect(card).toHaveTextContent("Using system defaults.");
    expect(within(card).queryByRole("textbox")).not.toBeInTheDocument();
    expect(api.risk.updateSettings).not.toHaveBeenCalled();
  });

  it("keeps independent sections available when Watcher or risk APIs fail and supports retry", async () => {
    vi.mocked(api.marketWatcher.monitoring).mockRejectedValueOnce(
      new Error("Unavailable"),
    );
    vi.mocked(api.risk.settings).mockRejectedValue(new Error("Unavailable"));
    render(<SettingsPage />);
    await screen.findByText("Risk settings unavailable.");
    expect(
      await screen.findByText("Strategy monitoring unavailable."),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("Symbol for slot 1")).toHaveValue(
      "BTCUSDT",
    );
    expect(screen.getByTestId("settings-posture-execution")).toHaveTextContent(
      "Confirmed",
    );
    expect(
      screen.getByTestId("settings-notification-context"),
    ).toHaveTextContent("Unavailable");
    fireEvent.click(
      screen.getByRole("button", { name: "Retry strategy monitoring" }),
    );
    await screen.findByText("Version 2 · Active paper version");
    expect(screen.getByTestId("settings-risk-summary")).toHaveTextContent(
      "Risk settings unavailable.",
    );
  });

  it("shows an empty monitoring state without inventing active strategy versions", async () => {
    vi.mocked(api.marketWatcher.monitoring).mockResolvedValue(
      makeWatcherMonitoringSnapshot({ symbols_monitored: [] }),
    );
    render(<SettingsPage />);
    await screen.findByText(
      "No approved or active paper strategy versions reported.",
    );
    expect(screen.getByTestId("settings-strategies-summary")).toHaveTextContent(
      "Setups detected in the last scan: 0",
    );
    expect(screen.getByText(/Reported monitoring universe:/)).toHaveTextContent(
      "No markets reported",
    );
    expect(api.strategies.listVersions).not.toHaveBeenCalled();
  });

  it("uses unverified posture and provider state when backend health is unavailable", async () => {
    runtime.health = null;
    runtime.providers = null;
    await loaded();
    expect(screen.getByTestId("settings-posture-execution")).toHaveTextContent(
      "Unverified",
    );
    expect(
      screen.getByTestId("settings-posture-real-trading"),
    ).toHaveTextContent("Unverified");
    expect(screen.getByTestId("settings-provider-health")).toHaveTextContent(
      "Provider health unavailable.",
    );
    expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
  });

  it("warns when backend health does not confirm paper-only mode", async () => {
    runtime.health = {
      execution_mode: "paper",
      real_trading_enabled: true,
    } as HealthResponse;
    await loaded();
    expect(screen.getByTestId("settings-posture-execution")).toHaveTextContent(
      "Paper-only mode not confirmed",
    );
    expect(
      screen.getByTestId("settings-posture-real-trading"),
    ).toHaveTextContent("Enabled — check system configuration");
  });

  it("edits only supported alert severity and never invokes network delivery or risk mutations", async () => {
    await loaded();
    expect(
      screen.getByTestId("settings-notification-context"),
    ).toHaveTextContent("BTCUSDT, ETHUSDT, SOLUSDT");
    expect(
      screen.getByTestId("settings-notification-context"),
    ).toHaveTextContent("Breakout");
    expect(screen.getByTestId("settings-telegram-state")).toHaveTextContent(
      "disabled",
    );
    expect(
      screen.queryByRole("button", { name: /send test/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Telegram delivery"),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Minimum alert severity"), {
      target: { value: "critical" },
    });
    await screen.findByText("Preferences saved.");
    expect(api.notifications.updatePreferences).toHaveBeenCalledExactlyOnceWith(
      { min_severity: "critical" },
    );
    expect(api.notifications.sendTest).not.toHaveBeenCalled();
    expect(api.alerts.testTelegram).not.toHaveBeenCalled();
    expect(api.alerts.deliverPending).not.toHaveBeenCalled();
    expect(api.risk.updateSettings).not.toHaveBeenCalled();
  });

  it("saves market changes through the existing revisioned watchlist API", async () => {
    const replace = vi
      .spyOn(api.watcherWatchlist, "replace")
      .mockResolvedValue({
        revision: 8,
        slots,
        max_enabled: 5,
        paper_only: true,
        updated_at: "2026-10-01T10:00:00Z",
      });
    await loaded();
    fireEvent.click(screen.getByLabelText("Enable slot 2"));
    fireEvent.click(screen.getByRole("button", { name: "Save watchlist" }));
    await waitFor(() =>
      expect(replace).toHaveBeenCalledExactlyOnceWith(
        [
          { symbol: "BTCUSDT", enabled: true },
          { symbol: "ETHUSDT", enabled: true },
        ],
        7,
      ),
    );
  });
});
