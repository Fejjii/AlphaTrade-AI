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
  /** Optional stable prefix for tab/panel ids; defaults to React.useId(). */
  idPrefix?: string;
}

function enabledItems(items: TabItem[]): TabItem[] {
  return items.filter((item) => !item.disabled);
}

function nextEnabledId(items: TabItem[], currentId: string, delta: number): string | null {
  const enabled = enabledItems(items);
  if (enabled.length === 0) return null;
  const idx = enabled.findIndex((item) => item.id === currentId);
  const base = idx >= 0 ? idx : 0;
  const next = (base + delta + enabled.length) % enabled.length;
  return enabled[next]?.id ?? null;
}

/** Lightweight accessible tabs (no Radix dependency). Manual activation + arrow keys. */
export function Tabs({
  items,
  value,
  onChange,
  className,
  "aria-label": ariaLabel,
  idPrefix,
}: TabsProps) {
  const autoPrefix = React.useId();
  const prefix = idPrefix ?? autoPrefix;
  const [focusedId, setFocusedId] = React.useState(value);
  const tabRefs = React.useRef(new Map<string, HTMLButtonElement>());

  React.useEffect(() => {
    setFocusedId(value);
  }, [value]);

  const focusTab = (id: string) => {
    setFocusedId(id);
    tabRefs.current.get(id)?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const enabled = enabledItems(items);
    if (enabled.length === 0) return;

    const current = focusedId || value || enabled[0].id;
    let nextId: string | null = null;

    switch (event.key) {
      case "ArrowRight":
        event.preventDefault();
        nextId = nextEnabledId(items, current, 1);
        break;
      case "ArrowLeft":
        event.preventDefault();
        nextId = nextEnabledId(items, current, -1);
        break;
      case "Home":
        event.preventDefault();
        nextId = enabled[0]?.id ?? null;
        break;
      case "End":
        event.preventDefault();
        nextId = enabled[enabled.length - 1]?.id ?? null;
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        if (!items.find((item) => item.id === current)?.disabled) {
          onChange(current);
        }
        return;
      default:
        return;
    }

    if (nextId) focusTab(nextId);
  };

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      data-tabs-prefix={prefix}
      onKeyDown={onKeyDown}
      className={cn(
        "inline-flex flex-wrap gap-1 rounded-control border border-border-subtle bg-surface-0 p-1",
        className,
      )}
    >
      {items.map((item) => {
        const selected = item.id === value;
        const tabDomId = `${prefix}-tab-${item.id}`;
        const panelDomId = `${prefix}-tabpanel-${item.id}`;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelDomId}
            disabled={item.disabled}
            id={tabDomId}
            tabIndex={focusedId === item.id ? 0 : -1}
            ref={(node) => {
              if (node) tabRefs.current.set(item.id, node);
              else tabRefs.current.delete(item.id);
            }}
            className={cn(
              "rounded-[calc(var(--radius-control)-2px)] px-3 py-1.5 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
              "disabled:cursor-not-allowed disabled:opacity-50",
              selected
                ? "bg-surface-2 text-text-primary"
                : "text-text-muted hover:text-text-secondary",
            )}
            onClick={() => {
              if (item.disabled) return;
              setFocusedId(item.id);
              onChange(item.id);
            }}
            onFocus={() => setFocusedId(item.id)}
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
  idPrefix,
}: {
  id: string;
  activeId: string;
  children: React.ReactNode;
  className?: string;
  /** Must match the Tabs `idPrefix` (or the same React tree useId) for aria linkage. */
  idPrefix?: string;
}) {
  const autoPrefix = React.useId();
  const prefix = idPrefix ?? autoPrefix;
  if (id !== activeId) return null;
  return (
    <div
      role="tabpanel"
      id={`${prefix}-tabpanel-${id}`}
      aria-labelledby={`${prefix}-tab-${id}`}
      className={className}
    >
      {children}
    </div>
  );
}
