"use client";

import { ChevronDown, RefreshCw, UserRound } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { resolvePageIdentity } from "@/components/layout/navigation-config";
import { StatusStrip } from "@/components/layout/StatusStrip";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { FreshnessPill } from "@/components/ui/freshness-pill";
import { IconButton } from "@/components/ui/icon-button";
import { useAppContext } from "@/contexts/AppContext";
import { useAuth } from "@/contexts/AuthContext";
import { useShellFreshness } from "@/contexts/ShellFreshnessContext";
import { cn } from "@/lib/utils";

type TopBarProps = {
  onOpenCommandMenu?: () => void;
};

export function TopBar({ onOpenCommandMenu }: TopBarProps) {
  const pathname = usePathname();
  const identity = resolvePageIdentity(pathname);
  const { refreshStatus, loading, providers } = useAppContext();
  const { user, organization, logout } = useAuth();
  // Providers unknown (null) must never look like a healthy "0 mock" (FP2-110).
  const mockCount = providers ? providers.providers.filter((p) => p.is_mock).length : null;
  const { freshness } = useShellFreshness();
  const [accountOpen, setAccountOpen] = useState(false);
  const accountWrapRef = useRef<HTMLDivElement>(null);
  const accountTriggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!accountOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!accountWrapRef.current?.contains(event.target as Node)) {
        setAccountOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setAccountOpen(false);
      // Restore focus to the account trigger after Escape closes the menu.
      queueMicrotask(() => {
        accountTriggerRef.current?.focus();
      });
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [accountOpen]);

  return (
    <header className="sticky top-0 z-30 overflow-x-hidden border-b border-border-subtle bg-surface-0/90 backdrop-blur">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 px-gutter py-3 lg:gap-3 lg:px-gutter-lg">
        <div className="min-w-0 flex-1" data-testid="topbar-page-identity">
          <p className="truncate text-sm font-semibold text-text-primary">{identity.title}</p>
          {identity.subtitle ? (
            <p className="truncate text-caption text-text-muted" data-testid="topbar-page-subtitle">
              <span>{identity.primaryLabel}</span>
              <span aria-hidden="true"> / </span>
              <span>{identity.subtitle}</span>
            </p>
          ) : null}
        </div>

        <div className="flex max-w-full min-w-0 flex-wrap items-center justify-end gap-1.5 sm:gap-2">
          <div data-testid="topbar-freshness" className="hidden sm:inline-flex">
            {freshness.state ? (
              <FreshnessPill state={freshness.state} ageLabel={freshness.ageLabel} />
            ) : (
              <span className="rounded-control border border-border-subtle px-2 py-1 text-caption text-text-muted">
                Freshness unavailable
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={onOpenCommandMenu}
            className="hidden rounded-control border border-border-subtle px-2 py-1.5 text-caption text-text-muted hover:bg-surface-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus md:inline-flex"
            aria-label="Open command menu"
          >
            Search ⌘K
          </button>

          <span className="hidden lg:inline-flex" data-testid="topbar-providers-chip">
            {mockCount == null ? (
              <StatusBadge label="Providers unknown" tone="warn" />
            ) : (
              <StatusBadge label={`${mockCount} mock`} tone="info" />
            )}
          </span>

          <IconButton
            label="Refresh status"
            variant="ghost"
            onClick={() => void refreshStatus()}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          </IconButton>

          <div className="relative" ref={accountWrapRef} data-testid="topbar-account-control">
            <button
              ref={accountTriggerRef}
              type="button"
              className={cn(
                "inline-flex min-h-11 max-w-[11rem] items-center gap-1.5 rounded-control border border-border-subtle px-2 py-1.5 text-caption",
                "text-text-secondary hover:bg-surface-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
              )}
              aria-haspopup="menu"
              aria-expanded={accountOpen}
              aria-controls={menuId}
              aria-label="Account menu"
              onClick={() => setAccountOpen((open) => !open)}
            >
              <UserRound className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="hidden min-w-0 truncate sm:inline">
                {user?.email ?? "Signed in"}
              </span>
              <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            </button>
            {accountOpen ? (
              <div
                id={menuId}
                role="menu"
                aria-label="Account"
                className="absolute right-0 z-40 mt-2 w-64 rounded-control border border-border-subtle bg-surface-0 p-2 shadow-elevation2"
              >
                <div className="border-b border-border-subtle px-2 pb-2 mb-2">
                  <p className="truncate text-sm text-text-primary">{user?.email ?? "Signed in"}</p>
                  <p className="truncate text-caption text-text-muted">
                    {organization?.name ?? "Tenant"}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  role="menuitem"
                  onClick={() => {
                    setAccountOpen(false);
                    void logout();
                  }}
                >
                  Log out
                </Button>
              </div>
            ) : null}
          </div>

          <KillSwitchButton compact />
        </div>
      </div>
      <StatusStrip />
    </header>
  );
}
