import Link from "next/link";
import type { ReactNode } from "react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { StatusBadge } from "@/components/StatusBadge";
import {
  WorkflowFreshnessAdapter,
  type FreshnessSourceInput,
} from "@/components/workflows";
import type { SafetyPostureDisplay } from "@/components/workflows/safetyPostureDisplay";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { RiskBlock } from "@/components/ui/risk-block";

const PORTFOLIO_NAV = [
  { href: "/portfolio", label: "Portfolio overview" },
  { href: "/positions", label: "Positions" },
  { href: "/risk", label: "Risk settings" },
] as const;

type PortfolioHubChromeProps = {
  title: string;
  description: string;
  posture: SafetyPostureDisplay;
  providerMode: string;
  freshnessSources: FreshnessSourceInput[];
  attentionSummary: string | null;
  attentionTone?: "ok" | "warn" | "blocked" | "muted";
  riskBlocked?: boolean;
  riskBlockReason?: string | null;
  testId?: string;
  activeHref?: string;
  children: ReactNode;
};

export function PortfolioHubChrome({
  title,
  description,
  posture,
  providerMode,
  freshnessSources,
  attentionSummary,
  attentionTone = "muted",
  riskBlocked = false,
  riskBlockReason = null,
  testId = "portfolio-command-centre",
  activeHref = "/portfolio",
  children,
}: PortfolioHubChromeProps) {
  return (
    <div className="space-y-section pb-24 md:pb-section" data-testid={testId}>
      <WorkflowFreshnessAdapter sources={freshnessSources} />

      <PageHeader
        title={title}
        description={description}
        meta={<PaperModeIndicator active={posture.paperConfirmed} />}
      />

      <div className="flex flex-wrap items-center gap-2" data-testid="portfolio-hub-safety">
        <StatusBadge
          label={posture.executionLabel}
          tone={
            posture.paperConfirmed
              ? "paper"
              : posture.kind === "safety_conflict"
                ? "blocked"
                : "warn"
          }
        />
        <StatusBadge label={`providers: ${providerMode}`} tone="muted" />
        <StatusBadge
          label={posture.realTradingLabel}
          tone={
            posture.realTradingVariant === "success"
              ? "healthy"
              : posture.realTradingVariant === "danger"
                ? "blocked"
                : "warn"
          }
        />
        <StatusBadge
          label={posture.runtimeBadgeLabel}
          tone={
            posture.runtimeBadgeVariant === "paper"
              ? "paper"
              : posture.runtimeBadgeVariant === "danger"
                ? "blocked"
                : "warn"
          }
        />
        <KillSwitchButton />
      </div>

      {posture.conflictMessage ? (
        <p className="text-sm text-danger" role="alert" data-testid="portfolio-safety-conflict">
          {posture.conflictMessage}
        </p>
      ) : null}

      {attentionSummary ? (
        <div
          role="status"
          data-testid="portfolio-risk-attention"
          className={
            attentionTone === "blocked"
              ? "rounded-control border border-danger-border bg-danger-muted/40 px-3 py-3 text-sm text-danger"
              : attentionTone === "warn"
                ? "rounded-control border border-warning-border bg-warning-muted/40 px-3 py-3 text-sm text-warning"
                : attentionTone === "ok"
                  ? "rounded-control border border-success-border bg-success-muted/40 px-3 py-3 text-sm text-success"
                  : "rounded-control border border-border-subtle bg-surface-1 px-3 py-3 text-sm text-text-secondary"
          }
        >
          <p className="font-medium text-text-primary">Primary risk condition</p>
          <p className="mt-1" data-testid="portfolio-risk-attention-summary">
            {attentionSummary}
          </p>
        </div>
      ) : null}

      {riskBlocked ? (
        <div data-testid="portfolio-risk-block">
          <RiskBlock
            reason={
              riskBlockReason ??
              "Risk engine BLOCK is final. There is no override control on Portfolio."
            }
            ruleReference="risk_engine.BLOCK"
          />
        </div>
      ) : null}

      <nav
        aria-label="Portfolio command centre sections"
        className="flex flex-wrap gap-3 text-sm"
        data-testid="portfolio-hub-nav"
      >
        {PORTFOLIO_NAV.map((item) => {
          const active = item.href === activeHref;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={
                active
                  ? "font-medium text-text-primary underline"
                  : "text-text-secondary underline"
              }
              aria-current={active ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {children}
    </div>
  );
}
