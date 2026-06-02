import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AnalyticsPage from "@/app/(app)/analytics/page";

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      setups: {
        organization_id: "org",
        user_id: "user",
        date_range: {},
        setups: [
          {
            setup_type: "htf_trend_pullback",
            proposal_count: 2,
            paper_trade_count: 1,
            winning_paper_trades: 1,
            losing_paper_trades: 0,
            most_common_mistakes: ["fomo"],
            most_common_lessons: [],
          },
        ],
      },
      review: {
        total_journaled_trades: 3,
        win_count: 2,
        loss_count: 1,
        trades_after_daily_loss_warning: 0,
        trades_after_green_day_warning: 0,
        trades_blocked_by_risk_engine: 0,
        proposals_rejected_by_user: 0,
        proposals_needing_more_analysis: 0,
      },
      discipline: {
        score: 82,
        grade: "B",
        positive_behaviors: ["Stop loss usage"],
        negative_behaviors: [],
        improvement_suggestions: ["Journal every trade"],
      },
      risk: {
        risk_blocks_count: 1,
        daily_loss_warnings: 0,
        green_day_warnings: 0,
        overtrading_warnings: 0,
        revenge_trading_warnings: 0,
        proposals_rejected: 0,
        proposals_needs_more_analysis: 0,
        paper_orders_rejected: 0,
        approval_pending_count: 0,
        approval_approved_count: 1,
        journal_completion_rate: 0.5,
        triggered_rules: {},
      },
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("AnalyticsPage", () => {
  it("renders setup performance cards", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("HTF trend pullback")).toBeInTheDocument();
    expect(screen.getByText("Discipline score")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
  });
});
