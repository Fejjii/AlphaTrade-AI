"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import {
  firstActionableStep,
  type WorkflowStep,
  type WorkflowStepStatus,
} from "@/lib/workflow-steps";

const STATUS_DOT: Record<WorkflowStepStatus, string> = {
  complete: "border-emerald-500/40 bg-emerald-500/20 text-emerald-300",
  current: "border-sky-500/40 bg-sky-500/20 text-sky-300",
  blocked: "border-amber-500/40 bg-amber-500/20 text-amber-300",
  upcoming: "border-zinc-700 bg-zinc-900 text-zinc-500",
};

const STATUS_LABEL: Record<WorkflowStepStatus, string> = {
  complete: "Complete",
  current: "Next",
  blocked: "Blocked",
  upcoming: "Upcoming",
};

export function WorkflowStepper({ steps }: { steps: WorkflowStep[] }) {
  const focus = firstActionableStep(steps);

  return (
    <section
      className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4"
      data-testid="workflow-stepper"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium text-zinc-200">Workflow</h2>
        <span className="text-xs text-zinc-500">Idea → Structure → Backtest → Paper → Lessons → Improve</span>
      </div>
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {steps.map((step, index) => (
          <li key={step.key} data-testid={`workflow-step-${step.key}`}>
            <Link
              href={step.href}
              className="flex items-start gap-3 rounded-lg border border-zinc-800 p-3 transition hover:border-zinc-600"
            >
              <span
                className={cn(
                  "flex h-6 w-6 flex-none items-center justify-center rounded-full border text-xs font-semibold",
                  STATUS_DOT[step.status],
                )}
              >
                {index + 1}
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-100">{step.label}</span>
                  <span
                    className="text-[10px] uppercase tracking-wide text-zinc-500"
                    data-testid={`workflow-step-status-${step.key}`}
                  >
                    {STATUS_LABEL[step.status]}
                  </span>
                </span>
                <span className="mt-0.5 block text-xs text-zinc-400">{step.nextAction}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
      {focus ? (
        <p className="mt-3 text-xs text-zinc-400" data-testid="workflow-next-action">
          What to do next: <span className="text-zinc-200">{focus.nextAction}</span>
        </p>
      ) : null}
    </section>
  );
}
