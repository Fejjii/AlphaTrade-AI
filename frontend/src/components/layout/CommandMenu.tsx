"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  PRIMARY_DESTINATIONS,
  SECONDARY_NAV,
  type NavLink,
} from "@/components/layout/navigation-config";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { cn } from "@/lib/utils";

type CommandMenuProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

type CommandEntry = {
  href: string;
  label: string;
  group: string;
};

function buildEntries(): CommandEntry[] {
  const entries: CommandEntry[] = PRIMARY_DESTINATIONS.map((d) => ({
    href: d.href,
    label: d.label,
    group: "Destinations",
  }));
  for (const group of SECONDARY_NAV) {
    for (const item of group.items as readonly NavLink[]) {
      if (entries.some((e) => e.href === item.href)) continue;
      entries.push({
        href: item.href,
        label: item.label,
        group: item.advanced ? "Advanced" : "Pages",
      });
    }
  }
  return entries;
}

export function CommandMenu({ open, onOpenChange }: CommandMenuProps) {
  const [query, setQuery] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const close = useCallback(() => onOpenChange(false), [onOpenChange]);
  useFocusTrap(panelRef, open, close);

  const entries = useMemo(() => buildEntries(), []);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (entry) => entry.label.toLowerCase().includes(q) || entry.href.toLowerCase().includes(q),
    );
  }, [entries, query]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(!open);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60]" data-testid="command-menu" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-black/60"
        aria-label="Close command menu"
        onClick={close}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command menu"
        className={cn(
          "relative mx-auto mt-[12vh] w-[min(32rem,calc(100%-2rem))] overflow-hidden rounded-card",
          "border border-border-subtle bg-surface-0 shadow-lg",
        )}
      >
        <div className="border-b border-border-subtle p-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Jump to a destination or page…"
            aria-label="Filter command menu"
            className="w-full rounded-control border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-focus"
          />
        </div>
        <ul className="max-h-80 overflow-y-auto p-2" aria-label="Command results">
          {filtered.length === 0 ? (
            <li className="px-3 py-4 text-sm text-text-muted">No matches</li>
          ) : (
            filtered.map((entry) => (
              <li key={`${entry.group}-${entry.href}`}>
                <Link
                  href={entry.href}
                  onClick={close}
                  className="flex items-center justify-between rounded-control px-3 py-2.5 text-sm hover:bg-surface-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  <span className="text-text-primary">{entry.label}</span>
                  <span className="text-caption text-text-muted">{entry.group}</span>
                </Link>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
