import * as React from "react";

import { cn } from "@/lib/utils";

/** Responsive content width + page section spacing. Does not change nav architecture. */
export function ContentContainer({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("mx-auto w-full min-w-0 max-w-content space-y-section", className)} {...props}>
      {children}
    </div>
  );
}

export function PageSection({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn("space-y-4", className)} {...props}>
      {children}
    </section>
  );
}
