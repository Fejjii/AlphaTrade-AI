import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AlertRoutingCard } from "@/components/AlertRoutingCard";
import type { AlertRoutingSummary } from "@/lib/api/types";

const baseRouting: AlertRoutingSummary = {
  alerts_enabled: true,
  telegram_enabled: false,
  webhook_enabled: false,
  external_delivery_enabled: false,
  paper_only: true,
  quiet_hours: { enabled: false, start: null, end: null, timezone: "UTC", source: "none" },
  severity_filters: ["worker: info+", "user: info+"],
  last_alert_created_at: null,
  last_alert_status: null,
  pending_alerts_count: 0,
  delivered_alerts_count: 0,
  failed_alerts_count: 0,
  market_watcher_configured: false,
  market_watcher_running: false,
  bridge_enabled: false,
  bridge_running: false,
  bridge_last_tick_at: null,
  bridge_last_decision: null,
  bridge_last_error: null,
  worker_enabled: false,
  worker_running: false,
  readiness: "ready",
  warnings: [],
  generated_at: "2026-06-28T12:00:00Z",
};

const degradedRouting: AlertRoutingSummary = {
  ...baseRouting,
  readiness: "degraded",
  bridge_enabled: true,
  bridge_running: false,
  bridge_last_decision: "failed",
  bridge_last_error: "Bridge tick failed.",
  warnings: ["Market watcher bridge is configured but not actively ticking."],
};

const blockedRouting: AlertRoutingSummary = {
  ...baseRouting,
  readiness: "blocked",
  telegram_enabled: true,
  warnings: ["Telegram alerts enabled but bot token is not configured."],
};

describe("AlertRoutingCard", () => {
  afterEach(() => cleanup());

  it("renders alerts card with Telegram disabled safely", () => {
    render(<AlertRoutingCard routing={baseRouting} />);
    expect(screen.getByTestId("alert-routing-card")).toBeInTheDocument();
    expect(screen.getByTestId("alert-routing-safety-badges")).toBeInTheDocument();
    expect(screen.getByText("Telegram disabled")).toBeInTheDocument();
    expect(screen.getByText("External delivery disabled")).toBeInTheDocument();
    expect(screen.getByText("Worker disabled")).toBeInTheDocument();
  });

  it("shows degraded bridge warning", () => {
    render(<AlertRoutingCard routing={degradedRouting} />);
    expect(screen.getByTestId("alert-routing-degraded-warning")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText(/Bridge tick failed/)).toBeInTheDocument();
  });

  it("shows blocked unsafe state", () => {
    render(<AlertRoutingCard routing={blockedRouting} />);
    expect(screen.getByTestId("alert-routing-blocked-warning")).toBeInTheDocument();
    expect(screen.getByText("Telegram enabled")).toBeInTheDocument();
    expect(screen.getByText(/Telegram alerts enabled but bot token/)).toBeInTheDocument();
  });
});
