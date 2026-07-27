import { describe, expect, it } from "vitest";

import { buildRiskPosture } from "@/components/portfolio/buildRiskPosture";
import { describeSafetyPosture } from "@/components/workflows/safetyPostureDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { DailyDisciplineSnapshot, KillSwitchStatus } from "@/lib/api/types";

function ok<T>(data: T): SourceResult<T> {
  return { data, available: true, error: null, fallbackUsed: false };
}

function failed<T>(error = "risk down"): SourceResult<T> {
  return { data: null, available: false, error, fallbackUsed: false };
}

function discipline(
  overrides: Partial<DailyDisciplineSnapshot> = {},
): DailyDisciplineSnapshot {
  return {
    date: "2026-07-27",
    timezone: "UTC",
    trades_today: 1,
    paper_trades_opened_today: 1,
    paper_trades_closed_today: 0,
    journal_entries_today: 0,
    realized_pnl_today_paper: "10",
    unrealized_pnl_paper: "5",
    net_pnl_today_paper: "15",
    daily_loss_limit: "100",
    daily_target: "200",
    loss_lock_active: false,
    green_day_protection_active: false,
    overtrading_warning_active: false,
    max_trades_per_day: 5,
    remaining_trades_allowed: 4,
    discipline_status: "calm",
    risk_settings_source: "user_risk_settings",
    pnl_sources: {},
    reasons: [],
    recommended_action: "Stay patient.",
    limitations: [],
    ...overrides,
  };
}

const posture = describeSafetyPosture("paper", false);
const killClear: KillSwitchStatus = {
  organization_id: "org",
  active: false,
  reason: null,
  activated_by: null,
  activated_at: null,
  deactivated_by: null,
  deactivated_at: null,
  version: 1,
  scope: "org",
  global_active: false,
  execution_blocked: false,
};

describe("buildRiskPosture", () => {
  it("returns loading/unavailable while discipline source is absent", () => {
    const view = buildRiskPosture({
      discipline: null,
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture,
    });
    expect(view.tradingState).toBe("unavailable");
    expect(view.tradingStateLabel).not.toMatch(/allowed/i);
  });

  it("never claims trading allowed when risk source failed", () => {
    const view = buildRiskPosture({
      discipline: failed(),
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture,
    });
    expect(view.tradingState).toBe("unavailable");
    expect(view.tradingStateLabel).toMatch(/unavailable/i);
    expect(view.attentionSummary).toMatch(/failed|unavailable/i);
  });

  it("reports allowed when discipline is calm and kill switch clear", () => {
    const view = buildRiskPosture({
      discipline: ok(discipline()),
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture,
    });
    expect(view.tradingState).toBe("allowed");
    expect(view.dailyLossStatus).toBe("clear");
    expect(view.cooldownStatus).toBe("clear");
    expect(view.showRiskBlock).toBe(false);
  });

  it("reports warning on caution / overtrading", () => {
    const view = buildRiskPosture({
      discipline: ok(
        discipline({
          discipline_status: "caution",
          overtrading_warning_active: true,
          recommended_action: "Slow down.",
        }),
      ),
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture,
    });
    expect(view.tradingState).toBe("warned");
    expect(view.cooldownStatus).toBe("active");
    expect(view.attentionSummary).toMatch(/Slow down/);
  });

  it("reports blocked when loss lock is active", () => {
    const view = buildRiskPosture({
      discipline: ok(
        discipline({
          loss_lock_active: true,
          discipline_status: "locked",
          reasons: ["Daily loss limit reached"],
        }),
      ),
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture,
    });
    expect(view.tradingState).toBe("blocked");
    expect(view.dailyLossStatus).toBe("active");
    expect(view.showRiskBlock).toBe(true);
    expect(view.activeBlockReasons.join(" ")).toMatch(/loss/i);
  });

  it("reports blocked when kill switch execution is blocked", () => {
    const view = buildRiskPosture({
      discipline: ok(discipline()),
      killSwitchStatus: { ...killClear, execution_blocked: true, reason: "Manual halt" },
      killSwitchError: null,
      posture,
    });
    expect(view.tradingState).toBe("blocked");
    expect(view.showRiskBlock).toBe(true);
    expect(view.activeBlockReasons.join(" ")).toMatch(/Kill switch/i);
  });

  it("does not claim allowed when kill switch status is unknown", () => {
    const view = buildRiskPosture({
      discipline: ok(discipline()),
      killSwitchStatus: null,
      killSwitchError: "kill switch down",
      posture,
    });
    expect(view.tradingState).toBe("unavailable");
    expect(view.tradingStateLabel).not.toMatch(/^Trading allowed$/i);
  });

  it("marks cooldown active when green-day protection is engaged", () => {
    const view = buildRiskPosture({
      discipline: ok(discipline({ green_day_protection_active: true })),
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture,
    });
    expect(view.cooldownStatus).toBe("active");
    expect(view.tradingState).toBe("warned");
  });

  it("preserves confirmed paper posture labels", () => {
    const view = buildRiskPosture({
      discipline: ok(discipline()),
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture,
    });
    expect(view.paperConfirmed).toBe(true);
    expect(view.executionModeLabel).toMatch(/PAPER/i);
    expect(view.realTradingLabel).toMatch(/disabled/i);
  });

  it("preserves unverified posture labels", () => {
    const unverified = describeSafetyPosture(null, null);
    const view = buildRiskPosture({
      discipline: ok(discipline()),
      killSwitchStatus: killClear,
      killSwitchError: null,
      posture: unverified,
    });
    expect(view.paperConfirmed).toBe(false);
    expect(view.executionModeLabel).toMatch(/unverified/i);
  });
});
