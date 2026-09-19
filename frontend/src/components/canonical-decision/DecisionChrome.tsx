"use client";

import type { ReactNode } from "react";

import { BindingNotice } from "@/components/canonical-decision/BindingNotice";
import { DecisionStepper } from "@/components/canonical-decision/DecisionStepper";
import { SafetyRail } from "@/components/canonical-decision/SafetyRail";
import { PageHeader } from "@/components/ui/page-header";
import { useAppContext } from "@/contexts/AppContext";
import { buildDecisionSteps } from "@/lib/canonical-decision/steps";
import type { DecisionStage } from "@/lib/canonical-decision/types";

export function DecisionChrome({
  title,
  description,
  current,
  eligibilityBlocked,
  children,
}: {
  title: string;
  description: string;
  current: DecisionStage;
  eligibilityBlocked?: boolean;
  children: ReactNode;
}) {
  const { killSwitchActive } = useAppContext();
  const steps = buildDecisionSteps({
    current,
    eligibilityBlocked,
    killSwitchActive,
  });

  return (
    <div className="space-y-6 pb-24 lg:pb-8" data-testid="canonical-decision-page">
      <PageHeader title={title} description={description} />
      <SafetyRail />
      <DecisionStepper steps={steps} />
      {children}
      <BindingNotice compact />
    </div>
  );
}
