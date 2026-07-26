import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataNumber } from "@/components/ui/data-number";
import type { ValidationCount } from "@/components/validate/types";

type ValidationSummaryCardProps = {
  label: string;
  count: ValidationCount;
  href: string;
  hint?: string;
  testId?: string;
};

export function ValidationSummaryCard({
  label,
  count,
  href,
  hint,
  testId,
}: ValidationSummaryCardProps) {
  const unavailable = count == null;
  return (
    <Card data-testid={testId ?? `validation-summary-${label.toLowerCase().replaceAll(" ", "-")}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-text-secondary">{label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {unavailable ? (
          <p className="text-lg font-semibold text-warning" data-testid="validation-summary-unavailable">
            unavailable
          </p>
        ) : (
          <DataNumber value={count} className="text-2xl font-semibold text-text-primary" />
        )}
        {hint ? <p className="text-caption text-text-muted">{hint}</p> : null}
        <Link
          href={href}
          className="inline-flex min-h-11 items-center text-sm text-text-primary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Open {label.toLowerCase()}
        </Link>
      </CardContent>
    </Card>
  );
}
