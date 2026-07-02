import type { BadgeProps } from "@/components/ui/badge";
import type {
  CalibrationLabel,
  DetectorTrustTier,
  DetectorVerdict,
} from "@/lib/api/types";

type Tone = NonNullable<BadgeProps["variant"]>;

export const VERDICT_META: Record<DetectorVerdict, { label: string; tone: Tone }> = {
  trusted: { label: "Trusted", tone: "success" },
  watch: { label: "Watch", tone: "muted" },
  improve: { label: "Improve", tone: "warning" },
  avoid_for_now: { label: "Avoid for now", tone: "danger" },
  needs_more_validation: { label: "Needs more validation", tone: "info" },
};

export const TRUST_META: Record<DetectorTrustTier, { label: string; tone: Tone }> = {
  none: { label: "No evidence", tone: "muted" },
  low: { label: "Low evidence", tone: "warning" },
  medium: { label: "Medium evidence", tone: "info" },
  high: { label: "High evidence", tone: "success" },
};

export const CALIBRATION_META: Record<CalibrationLabel, { label: string; tone: Tone }> = {
  well_calibrated: { label: "Well calibrated", tone: "success" },
  overconfident: { label: "Overconfident", tone: "warning" },
  underconfident: { label: "Underconfident", tone: "info" },
  insufficient_data: { label: "Not enough data", tone: "muted" },
};

/** Format a 0-1 rate as a whole-number percentage, or an em dash when absent. */
export function formatRate(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) {
    return "—";
  }
  return `${Math.round(rate * 100)}%`;
}

/** Format a quality score (0-100), or an em dash when absent. */
export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) {
    return "—";
  }
  return `${score}`;
}

export function labelize(value: string): string {
  return value.replace(/_/g, " ");
}
