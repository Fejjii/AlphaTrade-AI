import * as React from "react";

import { cn } from "@/lib/utils";

/** Raised surface panel for dense app sections (tokenized Card sibling). */
export function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-card border border-border-subtle bg-surface-raised p-4 lg:p-6",
        className,
      )}
      {...props}
    />
  );
}

export function PanelHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mb-3 flex items-start justify-between gap-3", className)} {...props} />;
}

/**
 * Panels are top-level page sections beneath the page `h1`, so their title is an
 * `h2`. Item headings inside a panel (a position symbol, for example) stay `h3`
 * and nest correctly instead of colliding with the panel title (FP2-222).
 */
export function PanelTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-section", className)} {...props} />;
}
