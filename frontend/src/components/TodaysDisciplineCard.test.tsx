import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TodaysDisciplineCard } from "@/components/TodaysDisciplineCard";
import type { DisciplineScoreResult, RiskBehaviorAnalytics } from "@/lib/api/types";

const discipline: DisciplineScoreResult = {
  score: 82,
  grade: "B",
  positive_behaviors: [],
  negative_behaviors: [],
  improvement_suggestions: ["Wait for confirmation before entering."],
};

const risk: RiskBehaviorAnalytics = {
  risk_blocks_count: 0,
  daily_loss_warnings: 1,
  green_day_warnings: 0,
  overtrading_warnings: 0,
  revenge_trading_warnings: 0,
  proposals_rejected: 0,
  proposals_needs_more_analysis: 0,
  paper_orders_rejected: 0,
  approval_pending_count: 0,
  approval_approved_count: 0,
  journal_completion_rate: 1,
  triggered_rules: {},
};

afterEach(cleanup);

describe("TodaysDisciplineCard", () => {
  it("shows discipline score and protection states", () => {
    render(<TodaysDisciplineCard discipline={discipline} risk={risk} tradesToday={3} />);
    expect(screen.getByTestId("discipline-score-badge")).toHaveTextContent("82/100");
    expect(screen.getByTestId("trades-today")).toHaveTextContent("3");
    expect(screen.getByTestId("discipline-next-action")).toHaveTextContent("confirmation");
  });

  it("uses calm wording without harsh phrasing", () => {
    const { container } = render(
      <TodaysDisciplineCard discipline={null} risk={null} tradesToday={null} />,
    );
    expect(container.textContent?.toLowerCase()).not.toContain("revenge");
    expect(container.textContent?.toLowerCase()).not.toContain("you failed");
  });
});
