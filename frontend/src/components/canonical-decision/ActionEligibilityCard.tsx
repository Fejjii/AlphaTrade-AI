import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskBlock } from "@/components/ui/risk-block";
import { eligibilityHeadline } from "@/lib/canonical-decision/eligibility";
import type { ActionEligibilityView } from "@/lib/canonical-decision/types";

export function ActionEligibilityCard({ eligibility }: { eligibility: ActionEligibilityView }) {
  const blocked = eligibility.state !== "eligible";
  return (
    <Card data-testid="action-eligibility-card">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Action eligibility</CardTitle>
          <StatusBadge
            label={eligibility.state}
            tone={blocked ? "blocked" : "success"}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="font-medium text-text-primary" data-testid="eligibility-headline">
          {eligibilityHeadline(eligibility)}
        </p>
        <p className="text-caption text-text-muted">
          Authority: {eligibility.authority.replaceAll("_", " ")}. Live executable: never.
          Paper-actionable: {eligibility.paperActionable ? "yes" : "no"}.
        </p>
        {blocked
          ? eligibility.explanations
              .filter((item) => item.blocking)
              .map((item) => (
                <RiskBlock
                  key={item.code}
                  reason={item.detail}
                  ruleReference={item.code}
                />
              ))
          : null}
        <ul className="flex flex-wrap gap-2">
          {eligibility.reasonCodes.map((code) => (
            <Badge key={code} variant={code === "eligible" ? "success" : "blocked"}>
              {code.replaceAll("_", " ")}
            </Badge>
          ))}
        </ul>
        <ul className="space-y-2" data-testid="eligibility-explanations">
          {eligibility.explanations.map((item) => (
            <li key={item.code}>
              <p className="font-medium text-text-primary">{item.title}</p>
              <p className="text-text-secondary">{item.detail}</p>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
