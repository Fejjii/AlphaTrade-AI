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
 *
 * Precedence:
 * 1. Explicit execution_blocked=true remains BLOCKED even if a later refresh failed
 *    (AppContext retains the previous status while setting killSwitchError).
 * 2. Any killSwitchError with no active block => UNAVAILABLE (stale clear is not clear).
 * 3. Non-null status with execution_blocked=false and no error => CLEAR.
 * 4. null + loading => LOADING.
 * 5. Otherwise => UNAVAILABLE.
 *
 * Only CLEAR may support "Trading allowed".
 */
export function resolveKillSwitchState(input: {
  killSwitchStatus: KillSwitchStatus | null;
  killSwitchError: string | null;
  killSwitchLoading: boolean;
}): KillSwitchResolution {
  const { killSwitchStatus, killSwitchError, killSwitchLoading } = input;
  if (killSwitchStatus?.execution_blocked === true) {
    return "blocked";
  }
  if (killSwitchError) {
    return "unavailable";
  }
  if (killSwitchStatus != null && killSwitchStatus.execution_blocked === false) {
    return "clear";
  }
  if (killSwitchLoading) {
    return "loading";
  }
  return "unavailable";
}

function killSwitchBlockReason(killSwitchStatus: KillSwitchStatus | null): string {
  return killSwitchStatus?.reason?.trim()
    ? `Kill switch blocking execution: ${killSwitchStatus.reason}`
    : "Kill switch is blocking execution";
}

type RiskPostureBaseFields = Pick<
  RiskPostureView,
  | "executionModeLabel"
  | "realTradingLabel"
  | "paperConfirmed"
  | "settingsHref"
  | "killSwitchResolution"
>;

/**
 * View for the discipline-unavailable branches (source loading, source failed, or
 * snapshot missing). Daily discipline values stay unavailable and are never invented.
 * An explicit kill-switch execution_blocked=true remains authoritative: the view is
 * BLOCKED with the stored kill-switch reason instead of a plain "unavailable" posture.
 */
function disciplineUnavailableView(params: {
  base: RiskPostureBaseFields;
  limitations: string[];
  killSwitchStatus: KillSwitchStatus | null;
  killSwitchError: string | null;
  unavailableLabel: string;
  unavailableSummary: string;
}): RiskPostureView {
  const { base, limitations, killSwitchStatus, killSwitchError } = params;
  const fields = {
    ...base,
    dailyLossStatus: "unavailable" as DailyLossStatus,
    dailyLossLabel: "Daily-loss status unavailable",
    cooldownStatus: "unavailable" as CooldownStatus,
    cooldownLabel: "Cooldown status unavailable",
    cooldownDetails: [],
    disciplineStatus: null,
    recommendedAction: null,
    limitations,
    dailyPnl: null,
    freshnessTimestamp: null,
  };

  if (base.killSwitchResolution !== "blocked") {
    return {
      ...fields,
      tradingState: "unavailable",
      tradingStateLabel: params.unavailableLabel,
      attentionSummary: params.unavailableSummary,
      activeBlockReasons: [],
      showRiskBlock: false,
      riskBlockReason: null,
    };
  }

  if (killSwitchError) {
    limitations.push(
      `Kill-switch refresh failed: ${killSwitchError}. Preserving last known BLOCK; freshness is unavailable.`,
    );
  }
  const blockReason = killSwitchBlockReason(killSwitchStatus);
  return {
    ...fields,
    tradingState: "blocked",
    tradingStateLabel: "Trading blocked",
    attentionSummary: blockReason,
    activeBlockReasons: [blockReason],
    showRiskBlock: true,
    riskBlockReason: blockReason,
  };
}

/**
 * Derive Portfolio risk posture from existing dashboard discipline + kill-switch fields.
 * Never invents "Trading allowed" when a risk source failed or kill-switch is unresolved.
 * Risk engine BLOCK / kill-switch execution_blocked remain authoritative, including when
 * the daily discipline source is loading, failed, or missing its snapshot.
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
    if (killSwitchResolution === "blocked") {
      limitations.push(
        "Daily discipline is still loading; discipline values are unavailable while the kill-switch BLOCK is shown.",
      );
    }
    return disciplineUnavailableView({
      base,
      limitations,
      killSwitchStatus,
      killSwitchError,
      unavailableLabel: "Risk posture loading",
      unavailableSummary: "Risk posture is still loading.",
    });
  }

  if (!discipline.available) {
    limitations.push(
      discipline.error
        ? `Risk state source failed: ${discipline.error}`
        : "Risk state source is unavailable.",
    );
    return disciplineUnavailableView({
      base,
      limitations,
      killSwitchStatus,
      killSwitchError,
      unavailableLabel: "Risk posture unavailable",
      unavailableSummary:
        "Trading allowance cannot be confirmed because the risk-state source failed.",
    });
  }

  const snapshot = disciplineSnapshot(discipline);
  if (!snapshot) {
    limitations.push("Dashboard returned no daily discipline snapshot.");
    return disciplineUnavailableView({
      base,
      limitations,
      killSwitchStatus,
      killSwitchError,
      unavailableLabel: "Risk posture unavailable",
      unavailableSummary: "Daily risk discipline snapshot is missing.",
    });
  }

  limitations.push(...snapshot.limitations);

  if (killSwitchResolution === "blocked" && killSwitchError) {
    limitations.push(
      `Kill-switch refresh failed: ${killSwitchError}. Preserving last known BLOCK; freshness is unavailable.`,
    );
  } else if (killSwitchResolution === "unavailable") {
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
    activeBlockReasons.push(killSwitchBlockReason(killSwitchStatus));
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
