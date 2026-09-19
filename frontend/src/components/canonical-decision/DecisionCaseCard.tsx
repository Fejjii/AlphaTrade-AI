import Link from "next/link";

import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { stageLabel } from "@/lib/canonical-decision/steps";
import type { DecisionCase } from "@/lib/canonical-decision/types";

export function DecisionCaseCard({ item }: { item: DecisionCase }) {
  return (
    <Card data-testid="decision-case-card">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle className="text-base">{item.title}</CardTitle>
          <StatusBadge label={stageLabel(item.stage)} tone="pending" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-text-secondary">{item.summary}</p>
        <div className="flex flex-wrap gap-2">
          <StatusBadge
            label={
              item.kind === "legacy_proposal"
                ? "compatibility proposal"
                : item.kind.replaceAll("_", " ")
            }
            tone={item.kind === "canonical_candidate" ? "success" : "muted"}
          />
          {item.candidate ? <ConfidenceBadge value={item.candidate.confidence} /> : null}
          {item.candidate ? (
            <StatusBadge
              label={`eligibility ${item.candidate.eligibility.state}`}
              tone={item.candidate.eligibility.state === "eligible" ? "success" : "blocked"}
            />
          ) : null}
        </div>
        <Link
          href={item.href}
          className="inline-flex min-h-11 items-center text-sm font-medium text-accent underline"
        >
          Open decision
        </Link>
      </CardContent>
    </Card>
  );
}
