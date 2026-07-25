import * as React from "react";

import { cn } from "@/lib/utils";

export function Divider({
  className,
  orientation = "horizontal",
  ...props
}: React.HTMLAttributes<HTMLHRElement> & { orientation?: "horizontal" | "vertical" }) {
  if (orientation === "vertical") {
    return (
      <div
        role="separator"
        aria-orientation="vertical"
        className={cn("mx-2 h-4 w-px self-stretch bg-border-subtle", className)}
        {...props}
      />
    );
  }
  return <hr className={cn("my-4 border-0 border-t border-border-subtle", className)} {...props} />;
}
