import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DisciplineAnalysisPanel } from "@/components/journal/DisciplineAnalysisPanel";
import { StructuredRuleEditor } from "@/components/strategy/StructuredRuleEditor";

describe("StructuredRuleEditor", () => {
  it("renders structured rule editor and testability score", () => {
    render(
      <StructuredRuleEditor
        rules={{
          primary_timeframe: "4h",
          entry_rules: [{ trigger_type: "ema_pullback" }],
          exit_rules: [{ rule_type: "fixed_stop" }],
          no_trade_rules: [],
        }}
        testability={{
          strategy_id: "s1",
          score: 82,
          band: "machine_testable",
          ready_for_backtest: true,
          missing_fields: [],
          has_structured_rules: true,
        }}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText(/Structured rule editor/)).toBeInTheDocument();
    expect(screen.getByTestId("testability-score")).toHaveTextContent("82/100");
    expect(screen.getByTestId("ready-badge")).toBeInTheDocument();
  });

  it("renders missing fields", () => {
    render(
      <StructuredRuleEditor
        rules={null}
        testability={{
          strategy_id: "s1",
          score: 35,
          band: "vague",
          ready_for_backtest: false,
          missing_fields: [{ field_key: "entry_trigger", label: "Entry trigger missing" }],
          has_structured_rules: false,
        }}
      />,
    );
    expect(screen.getByTestId("missing-fields")).toHaveTextContent("Entry trigger missing");
  });
});

describe("DisciplineAnalysisPanel", () => {
  it("renders human vs system discipline panel", () => {
    render(
      <DisciplineAnalysisPanel
        comparison={{
          trade_id: "t1",
          plan_adherence_score: 72,
          plan_adherence: {
            entry_followed_plan: 18,
            size_respected_risk: 20,
            stop_loss_respected: 15,
            profit_taking_followed: 10,
            emotion_controlled: 9,
            journal_completed: 0,
          },
          emotion_tags: [],
          notes: [],
          early_exit_flag: true,
          missed_runner: {
            early_exit_flag: true,
            recommended_lesson: "Review runner rules before entry.",
            confidence: "low",
          },
          stop_loss_analysis: {
            stop_violation_flag: false,
            lesson: "Stop discipline appears aligned.",
          },
          system_would_have_done: "System planned long BTCUSDT.",
        }}
      />,
    );
    expect(screen.getByTestId("discipline-panel")).toBeInTheDocument();
    expect(screen.getByTestId("early-exit-analysis")).toHaveTextContent("Early exit");
    expect(screen.getByTestId("stop-loss-analysis")).toHaveTextContent("Stop loss discipline");
  });
});
