import Link from "next/link";

import type { RiskPostureView } from "@/components/portfolio/buildRiskPosture";
import { formatMetricValue, pnlTone } from "@/components/portfolio/portfolioMetricDisplay";
import { StatusBadge } from "@/components/StatusBadge";
import { DataNumber } from "@/components/ui/data-number";
import { Panel, PanelHeader, PanelTitle } from "@/components/ui/panel";

function stateTone(state: RiskPostureView["tradingState"]): "healthy" | "warn" | "blocked" | "muted" {
  switch (state) {
    case "allowed":
      return "healthy";
    case "warned":
      return "warn";
    case "blocked":
      return "blocked";
    default:
      return "muted";
  }
}

export function RiskPosturePanel({ posture }: { posture: RiskPostureView }) {
  const dailyPnl = formatMetricValue(posture.dailyPnl);

  return (
    <section aria-labelledby="risk-posture-heading" data-testid="risk-posture-panel">
      <Panel>
        <PanelHeader>
          <div>
            <PanelTitle id="risk-posture-heading">Risk posture</PanelTitle>
            <p className="mt-1 text-sm text-text-muted">
              Read-only risk state from daily discipline and kill-switch status. Configuration stays
              on Risk settings.
            </p>
          </div>
          <span data-testid="risk-trading-state">
            <StatusBadge
              label={posture.tradingStateLabel}
              tone={stateTone(posture.tradingState)}
            />
          </span>
        </PanelHeader>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-control border border-border-subtle px-3 py-3">
            <p className="text-xs text-text-muted">Daily-loss status</p>
            <p className="mt-1 text-sm text-text-primary" data-testid="risk-daily-loss-status">
              {posture.dailyLossLabel}
            </p>
          </div>
          <div className="rounded-control border border-border-subtle px-3 py-3">
            <p className="text-xs text-text-muted">Cooldown status</p>
            <p className="mt-1 text-sm text-text-primary" data-testid="risk-cooldown-status">
              {posture.cooldownLabel}
            </p>
          </div>
          <div className="rounded-control border border-border-subtle px-3 py-3">
            <p className="text-xs text-text-muted">Discipline status</p>
            <p className="mt-1 text-sm text-text-primary" data-testid="risk-discipline-status">
              {posture.disciplineStatus ?? "Unavailable"}
            </p>
          </div>
          <div className="rounded-control border border-border-subtle px-3 py-3">
            <p className="text-xs text-text-muted">Execution mode</p>
            <p className="mt-1 text-sm text-text-primary" data-testid="risk-execution-mode">
              {posture.executionModeLabel}
            </p>
          </div>
          <div className="rounded-control border border-border-subtle px-3 py-3">
            <p className="text-xs text-text-muted">Real-trading-enabled</p>
            <p className="mt-1 text-sm text-text-primary" data-testid="risk-real-trading">
              {posture.realTradingLabel}
            </p>
          </div>
          <div className="rounded-control border border-border-subtle px-3 py-3">
            <p className="text-xs text-text-muted">Paper net P&amp;L today</p>
            {dailyPnl.kind === "value" ? (
              <DataNumber
                className="mt-1 text-sm font-semibold"
                value={dailyPnl.text}
                numeric={dailyPnl.numeric}
                tone={pnlTone(dailyPnl.numeric)}
                signed
                data-testid="risk-daily-pnl"
              />
            ) : (
              <p className="mt-1 text-sm text-text-muted" data-testid="risk-daily-pnl-unavailable">
                Unavailable
              </p>
            )}
          </div>
        </div>

        {posture.cooldownDetails.length > 0 ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-text-secondary" data-testid="risk-cooldown-details">
            {posture.cooldownDetails.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}

        {posture.activeBlockReasons.length > 0 ? (
          <div className="mt-3" data-testid="risk-block-reasons">
            <p className="text-sm font-medium text-text-primary">Active risk block reasons</p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-danger">
              {posture.activeBlockReasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {posture.recommendedAction ? (
          <p className="mt-3 text-sm text-text-secondary" data-testid="risk-recommended-action">
            Next attention: {posture.recommendedAction}
          </p>
        ) : null}

        <p className="mt-3 text-sm">
          <Link
            href={posture.settingsHref}
            className="underline text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            data-testid="risk-settings-link"
          >
            Open risk settings
          </Link>
          <span className="text-text-muted"> — configuration only; does not change enforcement here.</span>
        </p>
      </Panel>
    </section>
  );
}
