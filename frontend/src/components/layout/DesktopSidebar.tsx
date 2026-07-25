"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Command } from "lucide-react";

import {
  isPrimaryDestinationActive,
  PRIMARY_DESTINATIONS,
} from "@/components/layout/navigation-config";
import { StatusBadge } from "@/components/StatusBadge";
import { isPaperModeConfirmed } from "@/components/ui/paper-mode-indicator";
import { useSafetyPosture } from "@/contexts/AppContext";
import { appConfig } from "@/lib/config";
import { cn } from "@/lib/utils";

type DesktopSidebarProps = {
  onOpenCommandMenu?: () => void;
};

export function DesktopSidebar({ onOpenCommandMenu }: DesktopSidebarProps) {
  const pathname = usePathname();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const paperConfirmed = isPaperModeConfirmed(executionMode, realTradingEnabled);

  return (
    <aside
      data-testid="desktop-sidebar"
      className="hidden w-60 shrink-0 flex-col border-r border-border-subtle bg-surface-0 lg:flex"
      aria-label="Primary"
    >
      <div className="border-b border-border-subtle px-5 py-5">
        <p className="text-caption uppercase tracking-[0.16em] text-accent">{appConfig.appName}</p>
        <p className="mt-1 text-sm font-semibold text-text-primary">Trading Copilot</p>
      </div>

      <nav aria-label="Primary destinations" className="flex-1 space-y-1 overflow-y-auto p-3">
        {PRIMARY_DESTINATIONS.map((destination) => {
          const { href, label, icon: Icon, ariaLabel } = destination;
          const active = isPrimaryDestinationActive(pathname, destination);
          return (
            <Link
              key={destination.id}
              href={href}
              aria-label={ariaLabel}
              aria-current={active ? "page" : undefined}
              data-destination={destination.id}
              className={cn(
                "flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition-colors",
                "min-h-11 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                active
                  ? "bg-surface-2 text-text-primary"
                  : "text-text-muted hover:bg-surface-1 hover:text-text-secondary",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="space-y-2 border-t border-border-subtle p-3">
        <button
          type="button"
          onClick={onOpenCommandMenu}
          className={cn(
            "flex w-full items-center gap-2 rounded-control px-3 py-2 text-sm text-text-muted",
            "min-h-11 hover:bg-surface-1 hover:text-text-secondary",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
          )}
          aria-label="Open command menu"
        >
          <Command className="h-4 w-4" aria-hidden="true" />
          <span className="flex-1 text-left">Command menu</span>
          <kbd className="rounded border border-border-subtle px-1.5 py-0.5 text-caption text-text-muted">
            ⌘K
          </kbd>
        </button>
        <div className="flex items-center gap-2 px-1" data-testid="sidebar-environment-chip">
          <StatusBadge
            label={paperConfirmed ? "Paper" : "Unverified"}
            tone={paperConfirmed ? "paper" : "warn"}
          />
        </div>
      </div>
    </aside>
  );
}
