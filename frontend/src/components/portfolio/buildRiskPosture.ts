import type { SafetyPostureDisplay } from "@/components/workflows/safetyPostureDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import type { DailyDisciplineSnapshot, KillSwitchStatus } from "@/lib/api/types";

export type RiskTradingState = "allowed" | "warned" | "blocked" | "unavailable";

export type CooldownStatus = "clear" | "active" | "unavailable";

export type DailyLossStatus = "clear" | "active" | "unavailable";

export type KillSwitchResolution =
  | "clear"
  | "blocked"
  | "loading"
  | "unavailable";

export type RiskPostureView = {
  tradingState: RiskTradingState;
  tradingStateLabel: string;
  attentionSummary: string;
  dailyLossStatus: DailyLossStatus;
  dailyLossLabel: string;
  cooldownStatus: CooldownStatus;
  cooldownLabel: string;
  cooldownDetails: string[];
  activeBlockReasons: string[];
  disciplineStatus: string | null;
  recommendedAction: string | null;
  executionModeLabel: string;
  realTradingLabel: string;
  paperConfirmed: boolean;
  showRiskBlock: boolean;
  riskBlockReason: string | null;
  limitations: string[];
  dailyPnl: string | null;
  freshnessTimestamp: string | null;
  settingsHref: string;
  killSwitchResolution: KillSwitchResolution;
};

export type BuildRiskPostureInput = {
  discipline: SourceResult<DailyDisciplineSnapshot | null> | null | undefined;
  killSwitchStatus: KillSwitchStatus | null;
  killSwitchError: string | null;
  /** AppContext loading — null kill-switch with no error while loading is unverified. */
  killSwitchLoading: boolean;
  posture: SafetyPostureDisplay;
};

function disciplineSnapshot(
  discipline: SourceResult<DailyDisciplineSnapshot | null> | null | undefined,
): DailyDisciplineSnapshot | null {
  if (!discipline?.available) return null;
  return discipline.data ?? null;
}

/**
 * Resolve kill-switch state fail-closed.
 * null status never means clear. Only an explicit returned status with
 * execution_blocked=false may support "Trading allowed".
 */
export function resolveKillSwitchState(input: {
  killSwitchStatus: KillSwitchStatus | null;
  killSwitchError: string | null;
  killSwitchLoading: boolean;
}): KillSwitchResolution {
  const { killSwitchStatus, killSwitchError, killSwitchLoading } = input;
  if (killSwitchStatus != null) {
    return killSwitchStatus.execution_blocked ? "blocked" : "clear";
  }
  if (killSwitchError) return "unavailable";
  if (killSwitchLoading) return "loading";
  // null status with no error and not loading — still unresolved, never clear
  return "unavailable";
}

/**
 * Derive Portfolio risk posture from existing dashboard discipline + kill-switch fields.
 * Never invents "Trading allowed" when a risk source failed or kill-switch is unresolved.
 * Risk engine BLOCK / kill-switch execution_blocked remain authoritative.
 */
export function buildRiskPosture(input: BuildRiskPostureInput): RiskPostureView {
  const { discipline, killSwitchStatus, killSwitchError, killSwitchLoading, posture } = input;
  const limitations: string[] = [];
  const settingsHref = "/risk";
  const killSwitchResolution = resolveKillSwitchState({
    killSwitchStatus,
    killSwitchError,
    killSwitchLoading,
  });

  const base = {
    executionModeLabel: posture.executionLabel,
    realTradingLabel: posture.realTradingLabel,
    paperConfirmed: posture.paperConfirmed,
    settingsHref,
    killSwitchResolution,
  };

  if (!discipline) {
    return {
      ...base,
      tradingState: "unavailable",
      tradingStateLabel: "Risk posture loading",
      attentionSummary: "Risk posture is still loading.",
      dailyLossStatus: "unavailable",
      dailyLossLabel: "Daily-loss status unavailable",
      cooldownStatus: "unavailable",
      cooldownLabel: "Cooldown status unavailable",
      cooldownDetails: [],
      activeBlockReasons: [],
      disciplineStatus: null,
      recommendedAction: null,
      showRiskBlock: false,
      riskBlockReason: null,
      limitations,
      dailyPnl: null,
      freshnessTimestamp: null,
    };
  }

  if (!discipline.available) {
    limitations.push(
      discipline.error
        ? `Risk state source failed: ${discipline.error}`
        : "Risk state source is unavailable.",
    );
    return {
      ...base,
      tradingState: "unavailable",
      tradingStateLabel: "Risk posture unavailable",
      attentionSummary:
        "Trading allowance cannot be confirmed because the risk-state source failed.",
      dailyLossStatus: "unavailable",
      dailyLossLabel: "Daily-loss status unavailable",
      cooldownStatus: "unavailable",
      cooldownLabel: "Cooldown status unavailable",
      cooldownDetails: [],
      activeBlockReasons: [],
      disciplineStatus: null,
      recommendedAction: null,
      showRiskBlock: false,
      riskBlockReason: null,
      limitations,
      dailyPnl: null,
      freshnessTimestamp: null,
    };
  }

  const snapshot = disciplineSnapshot(discipline);
  if (!snapshot) {
    limitations.push("Dashboard returned no daily discipline snapshot.");
    return {
      ...base,
      tradingState: "unavailable",
      tradingStateLabel: "Risk posture unavailable",
      attentionSummary: "Daily risk discipline snapshot is missing.",
      dailyLossStatus: "unavailable",
      dailyLossLabel: "Daily-loss status unavailable",
      cooldownStatus: "unavailable",
      cooldownLabel: "Cooldown status unavailable",
      cooldownDetails: [],
      activeBlockReasons: [],
      disciplineStatus: null,
      recommendedAction: null,
      showRiskBlock: false,
      riskBlockReason: null,
      limitations,
      dailyPnl: null,
      freshnessTimestamp: null,
    };
  }

  limitations.push(...snapshot.limitations);

  if (killSwitchResolution === "unavailable") {
    limitations.push(
      killSwitchError
        ? `Kill-switch status unavailable: ${killSwitchError}. Trading allowed is not confirmed.`
        : "Kill-switch status is unresolved. Trading allowed is not confirmed.",
    );
  } else if (killSwitchResolution === "loading") {
    limitations.push(
      "Kill-switch status is still loading. Trading allowed is not confirmed.",
    );
  }

  const lossLock = snapshot.loss_lock_active;
  const greenDay = snapshot.green_day_protection_active;
  const overtrading = snapshot.overtrading_warning_active;
  const status = snapshot.discipline_status;
  const lockedByDiscipline = status === "locked" || status === "review_only";
  const killSwitchBlocked = killSwitchResolution === "blocked";

  const cooldownDetails: string[] = [];
  if (lossLock) cooldownDetails.push("Daily loss lock is active");
  if (greenDay) cooldownDetails.push("Green-day protection is engaged");
  if (overtrading) cooldownDetails.push("Overtrading frequency notice is active");
  if (snapshot.remaining_trades_allowed === 0) {
    cooldownDetails.push("No remaining trades allowed today under current limits");
  }

  const cooldownStatus: CooldownStatus = cooldownDetails.length > 0 ? "active" : "clear";
  const dailyLossStatus: DailyLossStatus = lossLock ? "active" : "clear";

  const activeBlockReasons: string[] = [];
  if (killSwitchBlocked) {
    activeBlockReasons.push(
      killSwitchStatus?.reason?.trim()
        ? `Kill switch blocking execution: ${killSwitchStatus.reason}`
        : "Kill switch is blocking execution",
    );
  }
  if (lossLock) activeBlockReasons.push("Daily loss lock is active");
  if (lockedByDiscipline) {
    activeBlockReasons.push(`Discipline status is ${status}`);
  }
  for (const reason of snapshot.reasons) {
    if (!activeBlockReasons.includes(reason)) activeBlockReasons.push(reason);
  }

  let tradingState: RiskTradingState;
  let tradingStateLabel: string;
  let attentionSummary: string;
  let showRiskBlock = false;
  let riskBlockReason: string | null = null;

  if (killSwitchBlocked || lossLock || lockedByDiscipline) {
    tradingState = "blocked";
    tradingStateLabel = "Trading blocked";
    attentionSummary =
      activeBlockReasons[0] ??
      snapshot.recommended_action ??
      "Trading is blocked under current risk rules.";
    showRiskBlock = true;
    riskBlockReason =
      activeBlockReasons.join("; ") ||
      "Risk engine BLOCK is final. There is no override on Portfolio.";
  } else if (killSwitchResolution === "loading") {
    tradingState = "unavailable";
    tradingStateLabel = "Trading allowance unverified";
    attentionSummary =
      "Kill-switch status is still loading, so trading allowed cannot be confirmed.";
  } else if (killSwitchResolution === "unavailable") {
    tradingState = "unavailable";
    tradingStateLabel = "Trading allowance unverified";
    attentionSummary =
      "Kill-switch status is unavailable, so trading allowed cannot be confirmed.";
  } else if (
    status === "caution" ||
    greenDay ||
    overtrading ||
    (snapshot.remaining_trades_allowed != null && snapshot.remaining_trades_allowed <= 1)
  ) {
    // killSwitchResolution === "clear" is required to reach here after the guards above
    tradingState = "warned";
    tradingStateLabel = "Trading warned";
    attentionSummary =
      snapshot.recommended_action ||
      cooldownDetails[0] ||
      "Risk conditions require attention before adding exposure.";
  } else if (status === "calm" && killSwitchResolution === "clear") {
    tradingState = "allowed";
    tradingStateLabel = "Trading allowed";
    attentionSummary =
      snapshot.recommended_action ||
      "No active risk block. Continue only within your paper risk rules.";
  } else {
    tradingState = "warned";
    tradingStateLabel = "Trading caution";
    attentionSummary =
      snapshot.recommended_action ||
      `Discipline status is ${status}. Review risk conditions before trading.`;
  }

  return {
    ...base,
    tradingState,
    tradingStateLabel,
    attentionSummary,
    dailyLossStatus,
    dailyLossLabel:
      dailyLossStatus === "active" ? "Daily-loss lock active" : "Daily-loss clear",
    cooldownStatus,
    cooldownLabel:
      cooldownStatus === "active" ? "Cooldown / protection active" : "Cooldown clear",
    cooldownDetails,
    activeBlockReasons,
    disciplineStatus: status,
    recommendedAction: snapshot.recommended_action,
    showRiskBlock,
    riskBlockReason,
    limitations,
    dailyPnl: snapshot.net_pnl_today_paper,
    freshnessTimestamp: snapshot.date ?? null,
  };
}
