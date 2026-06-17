import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TodaysDisciplineCard } from "@/components/TodaysDisciplineCard";
import type { DailyDisciplineSnapshot } from "@/lib/api/types";

const snapshot: DailyDisciplineSnapshot = {
  date: "2026-06-17",
  timezone: "UTC",
  trades_today: 3,
  paper_trades_opened_today: 2,
  paper_trades_closed_today: 1,
  journal_entries_today: 1,
  realized_pnl_today_paper: "-25.50",
  unrealized_pnl_paper: "10.00",
  net_pnl_today_paper: "-15.50",
  daily_loss_limit: "100",
  daily_target: null,
  loss_lock_active: true,
  green_day_protection_active: false,
  overtrading_warning_active: false,
  max_trades_per_day: 20,
  remaining_trades_allowed: 17,
  discipline_status: "locked",
  reasons: ["Daily loss limit reached for paper trading today."],
  recommended_action: "Step back and review today's paper results before taking more risk.",
  limitations: ["daily_target is not configured for this tenant."],
};

afterEach(cleanup);

describe("TodaysDisciplineCard", () => {
  it("shows backend trades today and daily PnL", () => {
    render(<TodaysDisciplineCard snapshot={snapshot} />);
    expect(screen.getByTestId("trades-today")).toHaveTextContent("3");
    expect(screen.getByTestId("daily-pnl-today")).toHaveTextContent("-15.5");
  });

  it("shows discipline status, reasons, and recommended action", () => {
    render(<TodaysDisciplineCard snapshot={snapshot} />);
    expect(screen.getByTestId("discipline-status-badge")).toHaveTextContent("locked");
    expect(screen.getByTestId("discipline-reasons")).toHaveTextContent("loss limit");
    expect(screen.getByTestId("discipline-next-action")).toHaveTextContent("Step back");
  });

  it("renders loss lock and limitations", () => {
    render(<TodaysDisciplineCard snapshot={snapshot} />);
    expect(screen.getByTestId("discipline-loss-protection")).toHaveTextContent("engaged");
    expect(screen.getByTestId("discipline-limitations")).toHaveTextContent("daily_target");
  });

  it("uses calm wording without harsh phrasing", () => {
    const { container } = render(<TodaysDisciplineCard snapshot={null} />);
    expect(container.textContent?.toLowerCase()).not.toContain("revenge");
    expect(container.textContent?.toLowerCase()).not.toContain("you failed");
  });
});
