"use client";

import { RefreshCw } from "lucide-react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { StatusStrip } from "@/components/layout/StatusStrip";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { useAppContext, useMockProviders } from "@/contexts/AppContext";
import { useAuth } from "@/contexts/AuthContext";
import { appConfig } from "@/lib/config";
import { StatusBadge } from "@/components/StatusBadge";

type TopBarProps = {
  onOpenCommandMenu?: () => void;
};

export function TopBar({ onOpenCommandMenu }: TopBarProps) {
  const { refreshStatus, loading } = useAppContext();
  const { user, organization, logout } = useAuth();
  const providers = useMockProviders();
  const mockCount = providers.filter((p) => p.is_mock).length;

  return (
    <header className="sticky top-0 z-30 border-b border-border-subtle bg-surface-0/90 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-2 px-gutter py-3 lg:gap-3 lg:px-gutter-lg">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-text-primary">{appConfig.appName}</p>
          <p className="truncate text-caption text-text-muted">
            {user?.email ?? "Signed in"} · {organization?.name ?? "Tenant"}
          </p>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-1.5 sm:gap-2">
          <button
            type="button"
            onClick={onOpenCommandMenu}
            className="hidden rounded-control border border-border-subtle px-2 py-1.5 text-caption text-text-muted hover:bg-surface-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus md:inline-flex"
            aria-label="Open command menu"
          >
            Search ⌘K
          </button>
          <span className="hidden sm:inline-flex">
            <StatusBadge label={`${mockCount} mock`} tone="info" />
          </span>
          <IconButton
            label="Refresh status"
            variant="ghost"
            onClick={() => void refreshStatus()}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          </IconButton>
          <Button variant="secondary" size="sm" onClick={() => void logout()}>
            Log out
          </Button>
          <KillSwitchButton compact />
        </div>
      </div>
      <StatusStrip />
    </header>
  );
}
