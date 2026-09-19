import { canExecutePaperOrder } from "@/lib/workflow";
import type {
  ApprovalRequest,
  CanonicalEligibilityRead,
  KillSwitchStatus,
  RiskCheckResult,
  TradeProposal,
} from "@/lib/api/types";
import type {
  ActionEligibilityView,
  EligibilityExplanation,
  EligibilityReasonCode,
} from "@/lib/canonical-decision/types";

const REASON_COPY: Record<
  EligibilityReasonCode,
  { title: string; detail: string; domain: EligibilityExplanation["domain"] }
> = {
  eligible: {
    title: "Paper-actionable (compatibility)",
    detail: "No blocking action gate was found on existing APIs. This is not canonical ActionEligibility.",
    domain: "action",
  },
  blocked_kill_switch: {
    title: "Kill switch is on",
    detail: "The organization kill switch blocks new paper execution. The risk engine BLOCK is final.",
    domain: "action",
  },
  blocked_daily_loss: {
    title: "Daily loss lock",
    detail: "Daily loss protection is blocking new paper entries.",
    domain: "action",
  },
  blocked_weekly_loss: {
    title: "Weekly loss limit",
    detail: "Weekly loss protection is blocking new paper entries.",
    domain: "action",
  },
  blocked_cooldown: {
    title: "Cooldown active",
    detail: "An overtrading or cooldown rule is blocking new paper entries.",
    domain: "action",
  },
  blocked_exposure: {
    title: "Exposure limit",
    detail: "Position or notional exposure limits block this paper action.",
    domain: "action",
  },
  blocked_portfolio_conflict: {
    title: "Portfolio conflict",
    detail: "An existing paper position or plan conflicts with this action.",
    domain: "action",
  },
  blocked_account_state: {
    title: "Account state",
    detail: "The paper account is not in a state that can accept this action.",
    domain: "action",
  },
  blocked_venue_state: {
    title: "Venue state",
    detail: "Demo/paper venue state is not ready for this action.",
    domain: "action",
  },
  blocked_data_quality: {
    title: "Data quality",
    detail: "Required market data is stale, fallback, or incomplete for actioning.",
    domain: "action",
  },
  blocked_basis: {
    title: "Cross-venue basis",
    detail: "Basis between evidence and execution venues is outside the allowed band.",
    domain: "action",
  },
  blocked_candidate_ttl: {
    title: "Candidate expired",
    detail: "The candidate validity window has elapsed.",
    domain: "action",
  },
  blocked_candidate_state: {
    title: "Candidate not actionable",
    detail: "The candidate is rejected, skipped, archived, or otherwise not ACTIVE.",
    domain: "action",
  },
  blocked_configuration: {
    title: "Unsafe configuration",
    detail: "Live/real-trading configuration is not paper-actionable. Live execution stays disabled.",
    domain: "configuration",
  },
  blocked_setup_not_confirmed: {
    title: "Setup not confirmed",
    detail: "Action eligibility requires a confirmed setup. Market quality is still independent.",
    domain: "action",
  },
  blocked_human_approval_required: {
    title: "Human approval required",
    detail: "A human must approve the exact paper plan. AI output cannot skip this step.",
    domain: "approval",
  },
  blocked_loss_acceptance: {
    title: "Loss acceptance required",
    detail: "Planned loss has not been accepted, so paper execution stays blocked.",
    domain: "approval",
  },
  blocked_risk_engine: {
    title: "Risk engine BLOCK",
    detail: "The deterministic risk engine returned BLOCK. There is no UI override.",
    domain: "action",
  },
  expired: {
    title: "Eligibility expired",
    detail: "A previous eligibility window is no longer valid and must be re-checked.",
    domain: "action",
  },
};

function explanation(code: EligibilityReasonCode, blocking: boolean, extra?: string): EligibilityExplanation {
  const copy = REASON_COPY[code];
  return {
    code,
    title: copy.title,
    detail: extra ? `${copy.detail} ${extra}` : copy.detail,
    domain: copy.domain,
    blocking,
  };
}

function riskRuleCodes(result: RiskCheckResult | null | undefined): EligibilityReasonCode[] {
  if (!result || result.action !== "block") return [];
  const joined = result.triggered_rules.map((rule) => `${rule.rule_id} ${rule.message}`.toLowerCase()).join(" ");
  const codes: EligibilityReasonCode[] = ["blocked_risk_engine"];
  if (joined.includes("kill")) codes.push("blocked_kill_switch");
  if (joined.includes("daily") && joined.includes("loss")) codes.push("blocked_daily_loss");
  if (joined.includes("weekly") && joined.includes("loss")) codes.push("blocked_weekly_loss");
  if (joined.includes("cooldown") || joined.includes("overtrad")) codes.push("blocked_cooldown");
  if (joined.includes("exposure") || joined.includes("position")) codes.push("blocked_exposure");
  return [...new Set(codes)];
}

export type EligibilityFacts = {
  killSwitchActive: boolean;
  killSwitch?: KillSwitchStatus | null;
  executionMode: string | null | undefined;
  realTradingEnabled: boolean | null | undefined;
  proposal?: TradeProposal | null;
  approval?: ApprovalRequest | null;
  candidateActionable?: boolean;
  setupConfirmed?: boolean;
  staleRequiredData?: boolean;
};

/**
 * Compatibility ActionEligibility projection from existing APIs.
 * Never claims to be ActionEligibilityService output.
 * live_executable is always false.
 */
export function projectActionEligibility(facts: EligibilityFacts): ActionEligibilityView {
  const codes: EligibilityReasonCode[] = [];

  if (facts.killSwitchActive || facts.killSwitch?.execution_blocked || facts.killSwitch?.active) {
    codes.push("blocked_kill_switch");
  }
  if (facts.realTradingEnabled === true || (facts.executionMode && facts.executionMode !== "paper")) {
    codes.push("blocked_configuration");
  }
  if (facts.setupConfirmed === false) {
    codes.push("blocked_setup_not_confirmed");
  }
  if (facts.candidateActionable === false) {
    codes.push("blocked_candidate_state");
  }
  if (facts.staleRequiredData) {
    codes.push("blocked_data_quality");
  }
  if (facts.proposal) {
    codes.push(...riskRuleCodes(facts.proposal.risk_result));
    const paper = canExecutePaperOrder(facts.proposal, facts.approval);
    if (!paper.allowed) {
      const reason = (paper.reason ?? "").toLowerCase();
      if (reason.includes("loss acceptance")) codes.push("blocked_loss_acceptance");
      if (reason.includes("approval") || reason.includes("pending")) {
        codes.push("blocked_human_approval_required");
      }
      if (reason.includes("risk engine") || facts.proposal.risk_result?.action === "block") {
        codes.push("blocked_risk_engine");
      }
    }
  } else if (facts.approval && facts.approval.status !== "approved") {
    codes.push("blocked_human_approval_required");
  }

  const unique = [...new Set(codes)];
  const blocking = unique.filter((code) => code !== "eligible");
  const state: ActionEligibilityView["state"] = blocking.includes("expired")
    ? "expired"
    : blocking.length > 0
      ? "blocked"
      : "eligible";
  const displayCodes: EligibilityReasonCode[] = blocking.length > 0 ? blocking : ["eligible"];

  return {
    authority: "compatibility_projection",
    state,
    paperActionable: state === "eligible",
    liveExecutable: false,
    reasonCodes: displayCodes,
    explanations: displayCodes.map((code) => explanation(code, code !== "eligible")),
    checkedAt: null,
    validUntil: null,
    killSwitchActive: Boolean(facts.killSwitchActive || facts.killSwitch?.active),
    humanApprovalSatisfied: facts.approval?.status === "approved",
  };
}

export function projectCanonicalEligibility(
  evaluation: CanonicalEligibilityRead,
  facts: Pick<
    EligibilityFacts,
    "killSwitchActive" | "killSwitch" | "executionMode" | "realTradingEnabled"
  >,
): ActionEligibilityView {
  const overlay = projectActionEligibility({
    killSwitchActive: facts.killSwitchActive,
    killSwitch: facts.killSwitch,
    executionMode: facts.executionMode,
    realTradingEnabled: facts.realTradingEnabled,
  });
  const rawCodes = evaluation.evaluation.eligibility.reason_codes ?? [];
  const known = new Set(Object.keys(REASON_COPY));
  const canonicalCodes = rawCodes.map((code) =>
    known.has(code) ? (code as EligibilityReasonCode) : "blocked_risk_engine",
  );
  const overlayBlocking = overlay.reasonCodes.filter((code) => code !== "eligible");
  const unique = [...new Set([...overlayBlocking, ...canonicalCodes])];
  const eligibilityState = evaluation.evaluation.eligibility.state;
  const expired =
    eligibilityState === "expired" || unique.includes("expired");
  const blocked = unique.length > 0 || eligibilityState === "blocked" || expired;
  const state: ActionEligibilityView["state"] = expired ? "expired" : blocked ? "blocked" : "eligible";
  const displayCodes: EligibilityReasonCode[] =
    state === "eligible" ? ["eligible"] : unique.length > 0 ? unique : ["blocked_risk_engine"];
  return {
    authority: "canonical",
    state,
    paperActionable: state === "eligible" && evaluation.evaluation.paper_actionable,
    liveExecutable: false,
    reasonCodes: displayCodes,
    explanations: displayCodes.map((code) =>
      code === "eligible"
        ? {
            code,
            title: "Paper-actionable (canonical)",
            detail:
              "ActionEligibilityService returned ELIGIBLE. Live executable stays false. Market quality still does not grant permission.",
            domain: "action" as const,
            blocking: false,
          }
        : explanation(code, true),
    ),
    checkedAt: evaluation.evaluation.eligibility.checked_at ?? null,
    validUntil: evaluation.evaluation.eligibility.valid_until ?? null,
    killSwitchActive: overlay.killSwitchActive,
    humanApprovalSatisfied: overlay.humanApprovalSatisfied,
  };
}

export function eligibilityHeadline(view: ActionEligibilityView): string {
  if (view.state === "eligible") {
    return view.authority === "canonical"
      ? "Eligible for paper action (canonical ActionEligibility)"
      : "Eligible for paper action (compatibility check)";
  }
  if (view.state === "expired") {
    return "Eligibility expired — re-check required";
  }
  const first = view.explanations.find((item) => item.blocking);
  return first ? `Blocked: ${first.title}` : "Blocked for paper action";
}
