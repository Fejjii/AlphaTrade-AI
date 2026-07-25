import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-pill border px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "border-border bg-surface-2 text-text-primary",
        success: "border-success-border bg-success-muted text-success",
        warning: "border-warning-border bg-warning-muted text-warning",
        danger: "border-danger-border bg-danger-muted text-danger",
        info: "border-info-border bg-info-muted text-info",
        muted: "border-border-subtle bg-surface-0 text-text-muted",
        paper: "border-paper-border bg-paper-muted text-paper",
        blocked: "border-blocked-border bg-blocked-muted text-blocked",
        stale: "border-stale-border bg-stale-muted text-stale",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}

export { badgeVariants };
