import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import type { DecisionStep } from "@/lib/canonical-decision/steps";
import { cn } from "@/lib/utils";

const TONE: Record<DecisionStep["status"], "success" | "pending" | "blocked" | "muted"> = {
  complete: "success",
  current: "pending",
  blocked: "blocked",
  upcoming: "muted",
};

export function DecisionStepper({
  steps,
  className,
}: {
  steps: DecisionStep[];
  className?: string;
}) {
  return (
    <nav
      aria-label="Canonical paper decision workflow"
      data-testid="decision-stepper"
      className={cn("overflow-x-auto", className)}
    >
      <ol className="flex min-w-max gap-2 pb-1 md:min-w-0 md:flex-wrap">
        {steps.map((step, index) => (
          <li key={step.key} className="min-w-[7.5rem] flex-1 md:min-w-[8.5rem]">
            <Link
              href={step.href}
              className={cn(
                "flex min-h-11 flex-col rounded-card border px-3 py-2 no-underline",
                step.status === "current"
                  ? "border-accent bg-accent/10"
                  : step.status === "blocked"
                    ? "border-blocked-border bg-blocked-muted"
                    : "border-border-subtle bg-surface-0",
              )}
              aria-current={step.status === "current" ? "step" : undefined}
            >
              <span className="text-caption text-text-muted">
                {index + 1}. {step.shortLabel}
              </span>
              <span className="text-xs font-medium text-text-primary">{step.label}</span>
              <span className="mt-1">
                <StatusBadge label={step.status} tone={TONE[step.status]} />
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </nav>
  );
}
