import { Clock, CloudOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type FreshnessState = "live" | "delayed" | "stale" | "fallback" | "unavailable" | "replay";

export interface FreshnessPillProps {
  state: FreshnessState;
  /** Human-readable age, e.g. "4m" */
  ageLabel?: string;
  className?: string;
}

const labels: Record<FreshnessState, string> = {
  live: "Live",
  delayed: "Delayed",
  stale: "Stale",
  fallback: "Fallback source",
  unavailable: "Unavailable",
  replay: "Replay fixture",
};

/** Data freshness indicator — always pairs icon + text (AT-039 §7.4). */
export function FreshnessPill({ state, ageLabel, className }: FreshnessPillProps) {
  const variant =
    state === "live" ? "success" : state === "unavailable" || state === "replay" ? "muted" : "stale";
  const Icon = state === "fallback" || state === "unavailable" || state === "replay" ? CloudOff : Clock;
  const text = ageLabel ? `${labels[state]} · ${ageLabel}` : labels[state];

  return (
    <Badge variant={variant} className={cn(className)} data-testid="freshness-pill">
      <Icon className="h-3 w-3" aria-hidden="true" />
      <span>{text}</span>
    </Badge>
  );
}
