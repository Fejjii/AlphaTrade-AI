"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface TabItem {
  id: string;
  label: string;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
  "aria-label"?: string;
}

/** Lightweight accessible tabs (no Radix dependency in Phase A). */
export function Tabs({ items, value, onChange, className, "aria-label": ariaLabel }: TabsProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex flex-wrap gap-1 rounded-control border border-border-subtle bg-surface-0 p-1",
        className,
      )}
    >
      {items.map((item) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={selected}
            disabled={item.disabled}
            id={`tab-${item.id}`}
            tabIndex={selected ? 0 : -1}
            className={cn(
              "rounded-[calc(var(--radius-control)-2px)] px-3 py-1.5 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
              "disabled:cursor-not-allowed disabled:opacity-50",
              selected
                ? "bg-surface-2 text-text-primary"
                : "text-text-muted hover:text-text-secondary",
            )}
            onClick={() => onChange(item.id)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({
  id,
  activeId,
  children,
  className,
}: {
  id: string;
  activeId: string;
  children: React.ReactNode;
  className?: string;
}) {
  if (id !== activeId) return null;
  return (
    <div
      role="tabpanel"
      id={`tabpanel-${id}`}
      aria-labelledby={`tab-${id}`}
      className={className}
    >
      {children}
    </div>
  );
}
