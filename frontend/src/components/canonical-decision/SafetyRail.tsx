"use client";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { RiskBadge } from "@/components/RiskBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { PaperModeIndicator, isPaperModeConfirmed } from "@/components/ui/paper-mode-indicator";
import { RiskBlock } from "@/components/ui/risk-block";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";

export function SafetyRail({ className }: { className?: string }) {
  const { killSwitchActive, killSwitchStatus } = useAppContext();
  const { executionMode, realTradingEnabled, postureKnown } = useSafetyPosture();
  const paperConfirmed = isPaperModeConfirmed(executionMode, realTradingEnabled);
  const realOn = realTradingEnabled === true;
  const blocked = killSwitchActive || killSwitchStatus?.execution_blocked === true;

  return (
    <section
      data-testid="decision-safety-rail"
      className={className}
      aria-label="Paper safety and kill switch"
    >
      <div className="flex flex-wrap items-center gap-2">
        <PaperModeIndicator active={paperConfirmed} />
        <StatusBadge
          label={postureKnown ? `Execution ${executionMode ?? "unknown"}` : "Execution unverified"}
          tone={paperConfirmed ? "success" : "blocked"}
        />
        <StatusBadge
          label={realOn ? "Real trading ON" : realTradingEnabled === false ? "Real trading OFF" : "Real trading ?"}
          tone={realOn ? "blocked" : realTradingEnabled === false ? "success" : "warn"}
        />
        <RiskBadge level={blocked ? "high" : "low"} />
        <KillSwitchButton compact />
      </div>
      {blocked ? (
        <div className="mt-3">
          <RiskBlock
            reason="Kill switch is active. New paper execution is blocked for the organization."
            ruleReference="kill_switch"
          />
        </div>
      ) : null}
      {realOn ? (
        <div className="mt-3">
          <RiskBlock
            reason="Real trading appears enabled. This workflow will not offer live execution controls."
            ruleReference="real_trading_enabled"
          />
        </div>
      ) : null}
      <p className="mt-3 text-caption text-text-secondary" data-testid="decision-human-approval-copy">
        Human approval is mandatory. An AI recommendation cannot approve a plan or place a paper
        order. Approval records authorization only and does not execute.
      </p>
    </section>
  );
}
