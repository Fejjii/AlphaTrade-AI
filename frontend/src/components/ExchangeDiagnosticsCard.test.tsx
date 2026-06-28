import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ExchangeDiagnosticsCard } from "@/components/ExchangeDiagnosticsCard";
import type { ExchangeDiagnosticsSummary } from "@/lib/api/types";

const readySummary: ExchangeDiagnosticsSummary = {
  exchange_mode: "paper_exchange_demo",
  execution_mode: "paper",
  real_trading_enabled: false,
  demo_active: true,
  provider_health: "healthy",
  worker_enabled: false,
  telegram_enabled: false,
  position_mode: "long_short_mode",
  leverage: {
    inst_id: "BTC-USDT",
    margin_mode: "cross",
    leverage: "3",
    probe_ok: true,
  },
  instrument: {
    symbol: "BTCUSDT",
    inst_id: "BTC-USDT",
    active: true,
    probe_ok: true,
  },
  venue_positions_count: 0,
  last_exchange_order_status: "filled",
  last_demo_mirror_result: "created",
  last_demo_mirror_error_code: null,
  last_demo_mirror_error_message: null,
  last_cancel_status: null,
  readiness: "ready",
  warnings: [],
  generated_at: "2026-06-28T12:00:00Z",
};

const blockedSummary: ExchangeDiagnosticsSummary = {
  ...readySummary,
  readiness: "blocked",
  venue_positions_count: 2,
  warnings: ["Open venue positions detected — resolve before demo trading."],
};

const degradedSummary: ExchangeDiagnosticsSummary = {
  ...readySummary,
  readiness: "degraded",
  provider_health: "degraded",
  last_demo_mirror_result: "failed",
  last_demo_mirror_error_code: "51008",
  last_demo_mirror_error_message: "Order price is out of range",
  warnings: ["Leverage probe failed."],
};

describe("ExchangeDiagnosticsCard", () => {
  afterEach(() => cleanup());

  it("renders diagnostics card with safety badges", () => {
    render(<ExchangeDiagnosticsCard diagnostics={readySummary} />);
    expect(screen.getByTestId("exchange-diagnostics-card")).toBeInTheDocument();
    expect(screen.getByTestId("exchange-safety-badges")).toBeInTheDocument();
    expect(screen.getByText("Paper only")).toBeInTheDocument();
    expect(screen.getByText("Real trading disabled")).toBeInTheDocument();
    expect(screen.getByText("Worker disabled")).toBeInTheDocument();
    expect(screen.getByText("Telegram disabled")).toBeInTheDocument();
    expect(screen.getByText("Mirrored successfully")).toBeInTheDocument();
  });

  it("shows blocked warning", () => {
    render(<ExchangeDiagnosticsCard diagnostics={blockedSummary} />);
    expect(screen.getByTestId("exchange-blocked-warning")).toBeInTheDocument();
    expect(screen.getByText("blocked")).toBeInTheDocument();
    expect(screen.getByText(/Open venue positions detected/)).toBeInTheDocument();
  });

  it("handles degraded provider response", () => {
    render(<ExchangeDiagnosticsCard diagnostics={degradedSummary} />);
    expect(screen.getByTestId("exchange-diagnostics-card")).toHaveTextContent("degraded");
    expect(screen.getByText("Mirror failed")).toBeInTheDocument();
    expect(screen.getByText(/Code 51008/)).toBeInTheDocument();
    expect(screen.getByText(/Leverage probe failed/)).toBeInTheDocument();
  });
});
