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

const JOURNAL_NAV = [
  { href: "/journal", label: "Journal hub" },
  { href: "/journal/import", label: "Import" },
  { href: "/lessons", label: "Lessons" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/journal/statistics", label: "Statistics" },
  { href: "/journal/comparison", label: "Human vs System" },
] as const;

type JournalHubChromeProps = {
  title: string;
  description: string;
  posture: SafetyPostureDisplay;
  providerMode: string;
  freshnessSources: FreshnessSourceInput[];
  testId?: string;
  children: ReactNode;
  activeHref?: string;
};

export function JournalHubChrome({
  title,
  description,
  posture,
  providerMode,
  freshnessSources,
  testId = "journal-hub-page",
  children,
  activeHref = "/journal",
}: JournalHubChromeProps) {
  return (
    <div className="space-y-section pb-24 md:pb-section" data-testid={testId}>
      <WorkflowFreshnessAdapter sources={freshnessSources} />

      <PageHeader
        title={title}
        description={description}
        meta={<PaperModeIndicator active={posture.paperConfirmed} />}
      />

      <div className="flex flex-wrap items-center gap-2" data-testid="journal-hub-safety">
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
        <p className="text-sm text-danger" role="alert" data-testid="journal-safety-conflict">
          {posture.conflictMessage}
        </p>
      ) : null}

      <nav aria-label="Journal hub sections" className="flex flex-wrap gap-3 text-sm">
        {JOURNAL_NAV.map((item) => {
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
