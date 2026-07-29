import Link from "next/link";
import type { ReactNode } from "react";

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
