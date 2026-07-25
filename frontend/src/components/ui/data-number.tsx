import * as React from "react";

import { cn } from "@/lib/utils";

export type DataNumberTone = "default" | "positive" | "negative" | "muted";

export interface DataNumberProps extends React.HTMLAttributes<HTMLSpanElement> {
  value: React.ReactNode;
  tone?: DataNumberTone;
  /** When true, prefix ▲/▼ for directional meaning (not color-only). */
  signed?: boolean;
  numeric?: number | null;
}

const toneClass: Record<DataNumberTone, string> = {
  default: "text-text-primary",
  positive: "text-positive",
  negative: "text-negative",
  muted: "text-text-muted",
};

/** Trading metrics with tabular numerals. */
export function DataNumber({
  value,
  tone = "default",
  signed = false,
  numeric,
  className,
  ...props
}: DataNumberProps) {
  const prefix =
    signed && numeric != null && numeric !== 0
      ? numeric > 0
        ? "▲ "
        : "▼ "
      : "";
  return (
    <span className={cn("font-data text-sm", toneClass[tone], className)} {...props}>
      {prefix}
      {value}
    </span>
  );
}
