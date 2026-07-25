"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  className?: string;
  side?: "top" | "bottom";
}

/**
 * Accessible tooltip: shows on focus/hover; content is not color-only.
 * Phase A native implementation — no new dependency.
 */
export function Tooltip({ content, children, className, side = "top" }: TooltipProps) {
  const [open, setOpen] = React.useState(false);
  const id = React.useId();

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {React.cloneElement(children, {
        "aria-describedby": open ? id : undefined,
        onFocus: (e: React.FocusEvent) => {
          setOpen(true);
          children.props.onFocus?.(e);
        },
        onBlur: (e: React.FocusEvent) => {
          setOpen(false);
          children.props.onBlur?.(e);
        },
      })}
      {open ? (
        <span
          id={id}
          role="tooltip"
          className={cn(
            "pointer-events-none absolute z-50 max-w-xs rounded-control border border-border bg-surface-2 px-2 py-1 text-caption text-text-primary shadow-elevation2",
            side === "top" ? "bottom-full left-1/2 mb-2 -translate-x-1/2" : "top-full left-1/2 mt-2 -translate-x-1/2",
            className,
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
