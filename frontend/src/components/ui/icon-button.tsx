import * as React from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface IconButtonProps extends Omit<ButtonProps, "size" | "children"> {
  label: string;
  children: React.ReactNode;
}

/** Accessible icon-only button — `label` is required for screen readers. */
export function IconButton({ label, className, children, ...props }: IconButtonProps) {
  return (
    <Button
      type="button"
      size="icon"
      aria-label={label}
      title={label}
      className={cn(className)}
      {...props}
    >
      {children}
    </Button>
  );
}
