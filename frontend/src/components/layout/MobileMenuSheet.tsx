"use client";

import { Command } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useRef } from "react";

import {
  getPrimaryDestination,
  isPrimaryDestinationActive,
  MOBILE_MENU_DESTINATION_IDS,
} from "@/components/layout/navigation-config";
import { useFocusTrap } from "@/hooks/useFocusTrap";
import { cn } from "@/lib/utils";

type MobileMenuSheetProps = {
  open: boolean;
  onClose: () => void;
  onOpenCommandMenu?: () => void;
};

export function MobileMenuSheet({ open, onClose, onOpenCommandMenu }: MobileMenuSheetProps) {
  const pathname = usePathname();
  const panelRef = useRef<HTMLDivElement>(null);
  const handleEscape = useCallback(() => onClose(), [onClose]);
  useFocusTrap(panelRef, open, handleEscape);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 lg:hidden"
      data-testid="mobile-menu-sheet"
      role="presentation"
    >
      <button
        type="button"
        aria-label="Close navigation menu"
        className="absolute inset-0 bg-black/60 motion-safe:transition-opacity"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="More destinations"
        className={cn(
          "absolute inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom,0px))] max-h-[70vh] overflow-y-auto",
          "rounded-t-card border border-border-subtle bg-surface-0 p-4 shadow-lg",
          "pb-[max(1rem,env(safe-area-inset-bottom,0px))]",
          "motion-reduce:transition-none",
        )}
      >
        <div className="mx-auto mb-4 h-1 w-10 rounded-pill bg-border-subtle" aria-hidden="true" />
        {onOpenCommandMenu ? (
          <button
            type="button"
            data-testid="mobile-menu-command"
            aria-label="Open command menu"
            onClick={() => {
              onClose();
              onOpenCommandMenu();
            }}
            className={cn(
              "mb-3 flex min-h-14 w-full items-center gap-3 rounded-control px-4 py-3 text-base font-medium",
              "text-text-secondary hover:bg-surface-1",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
            )}
          >
            <Command className="h-5 w-5 shrink-0" aria-hidden="true" />
            <span>Search / Command menu</span>
          </button>
        ) : null}
        <p className="mb-3 text-caption font-semibold uppercase tracking-wider text-text-muted">
          More
        </p>
        <ul className="space-y-2">
          {MOBILE_MENU_DESTINATION_IDS.map((id) => {
            const destination = getPrimaryDestination(id);
            const { href, label, icon: Icon, ariaLabel } = destination;
            const active = isPrimaryDestinationActive(pathname, destination);
            return (
              <li key={id}>
                <Link
                  href={href}
                  aria-label={ariaLabel}
                  aria-current={active ? "page" : undefined}
                  data-destination={id}
                  onClick={onClose}
                  className={cn(
                    "flex min-h-14 items-center gap-3 rounded-control px-4 py-3 text-base font-medium",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                    active
                      ? "bg-surface-2 text-text-primary"
                      : "text-text-secondary hover:bg-surface-1",
                  )}
                >
                  <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                  <span>{label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
