"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { RiskBadge } from "@/components/RiskBadge";
import {
  resolveExecutionDisplay,
  resolveRiskDisplay,
} from "@/components/layout/status-strip-state";
import { StatusBadge } from "@/components/StatusBadge";
import { IconButton } from "@/components/ui/icon-button";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { cn } from "@/lib/utils";

const ADVICE_DISMISS_KEY = "alphatrade.statusStrip.adviceDismissed";

/**
 * Compact top-bar status strip consolidating paper-mode + advice messaging.
 * Paper mode remains fail-closed from verified runtime posture.
 */
export function StatusStrip({ className }: { className?: string }) {
  const { killSwitchStatus, killSwitchError, loading } = useAppContext();
  const { executionMode, realTradingEnabled, postureKnown } = useSafetyPosture();
  const execution = resolveExecutionDisplay(executionMode, realTradingEnabled, postureKnown);
  const risk = resolveRiskDisplay({
    killSwitchStatus,
    killSwitchError,
    statusLoading: loading,
  });
  const [adviceDismissed, setAdviceDismissed] = useState(false);

  useEffect(() => {
    try {
      setAdviceDismissed(sessionStorage.getItem(ADVICE_DISMISS_KEY) === "1");
    } catch {
      setAdviceDismissed(false);
    }
  }, []);

  const dismissAdvice = () => {
    try {
      sessionStorage.setItem(ADVICE_DISMISS_KEY, "1");
    } catch {
      /* sessionStorage may be unavailable */
    }
    setAdviceDismissed(true);
  };

  return (
    <div
      data-testid="status-strip"
      className={cn(
        "flex flex-wrap items-center gap-2 border-b border-border-subtle bg-surface-1/80 px-gutter py-2 text-caption lg:px-gutter-lg",
        className,
      )}
    >
      <PaperModeIndicator active={execution.paperConfirmed} />
      <span data-testid="status-strip-execution">
        <StatusBadge label={execution.label} tone={execution.tone} />
      </span>
      <StatusBadge
        label={
          realTradingEnabled === true
            ? "Real ON"
            : realTradingEnabled === false
              ? "Real OFF"
              : "Real ?"
        }
        tone={
          realTradingEnabled === true
            ? "blocked"
            : realTradingEnabled === false
              ? "success"
              : "warn"
        }
      />
      <span data-testid="status-strip-risk">
        <RiskBadge level={risk.level} />
      </span>
      {!adviceDismissed ? (
        <div
          className="flex min-w-0 flex-1 items-center gap-2 text-text-muted"
          data-testid="status-strip-advice"
        >
          <p className="min-w-0 flex-1 truncate">
            Not financial advice. Paper-only research — simulated results do not guarantee
            performance.
          </p>
          <IconButton
            label="Dismiss advice notice for this session"
            variant="ghost"
            onClick={dismissAdvice}
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </IconButton>
        </div>
      ) : null}
    </div>
  );
}
