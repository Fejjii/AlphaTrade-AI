import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { SourceResult } from "@/components/workflows";
import type { RiskBehaviorAnalytics } from "@/lib/api/types";

import { RiskBehaviourCounters } from "./RiskBehaviourCounters";

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

const data: RiskBehaviorAnalytics = {
  risk_blocks_count: 1,
  daily_loss_warnings: 3,
  green_day_warnings: 0,
  overtrading_warnings: 2,
  revenge_trading_warnings: 4,
  proposals_rejected: 0,
  proposals_needs_more_analysis: 0,
  paper_orders_rejected: 0,
  approval_pending_count: 0,
  approval_approved_count: 0,
  journal_completion_rate: 0.5,
  triggered_rules: {},
};

describe("RiskBehaviourCounters", () => {
  afterEach(() => cleanup());

  it("labels values as counts and never implies profitability", () => {
    render(<RiskBehaviourCounters source={ok(data)} />);
    expect(screen.getByTestId("risk-behaviour-counts-caption")).toHaveTextContent(
      /warning counts, not performance/i,
    );
    expect(screen.getByTestId("risk-behaviour-revenge")).toHaveTextContent("4");
    expect(screen.getByTestId("risk-behaviour-daily-loss")).toHaveTextContent("3");
    expect(screen.getByTestId("risk-behaviour-counts-caption")).toHaveTextContent(
      /never infer profitability/i,
    );
    expect(screen.queryByTestId("risk-behaviour-revenge")?.textContent).not.toMatch(/profit/i);
  });
});
