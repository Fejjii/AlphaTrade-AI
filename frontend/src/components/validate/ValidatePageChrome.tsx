import Link from "next/link";
import type { ReactNode } from "react";

import {
  WorkflowFreshnessAdapter,
  type FreshnessSourceInput,
} from "@/components/workflows";
import type { SafetyPostureDisplay } from "@/components/workflows/safetyPostureDisplay";
import { PageHeader } from "@/components/ui/page-header";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { RiskBlock } from "@/components/ui/risk-block";
import { validateHubHref } from "@/components/validate/validationLinks";

const STAGE_NAV = [
  { href: validateHubHref(), label: "Validate hub" },
  { href: "/paper-validation/drafts", label: "Drafts" },
  { href: "/paper-validation/candidates", label: "Candidates" },
  { href: "/paper-validation/run-plans", label: "Run plans" },
  { href: "/paper-validation/run-sessions", label: "Run sessions" },
  { href: "/validation-priority", label: "Priority" },
  { href: "/research-validation", label: "Research (advanced)" },
] as const;

type ValidatePageChromeProps = {
  title: string;
  description: string;
  posture: SafetyPostureDisplay;
  providerMode: string;
  freshnessSources: FreshnessSourceInput[];
  testId: string;
  children: ReactNode;
  riskBlocked?: boolean;
  riskSummary?: string | null;
  activeHref?: string;
};

export function ValidatePageChrome({
  title,
  description,
  posture,
  providerMode,
  freshnessSources,
  testId,
  children,
  riskBlocked = false,
  riskSummary = null,
  activeHref,
}: ValidatePageChromeProps) {
  void providerMode;

  return (
    <div className="space-y-section pb-24 md:pb-section" data-testid={testId}>
      <WorkflowFreshnessAdapter sources={freshnessSources} />

      <PageHeader
        title={title}
        description={description}
        meta={<PaperModeIndicator active={posture.paperConfirmed} />}
      />

      {posture.conflictMessage ? (
        <p className="text-sm text-danger" role="alert" data-testid="validate-safety-conflict">
          {posture.conflictMessage}
        </p>
      ) : null}

      {riskBlocked ? (
        <div data-testid="validate-risk-block">
          <RiskBlock
            reason={
              riskSummary ??
              "Risk engine BLOCK is final. There is no override control on Validate surfaces."
            }
            ruleReference="risk_engine.BLOCK"
          />
        </div>
      ) : null}

      <nav
        aria-label="Validate pipeline stages"
        className="flex flex-wrap gap-3 text-sm"
        data-testid="validate-stage-nav"
      >
        {STAGE_NAV.map((item) => {
          const active = activeHref === item.href;
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
