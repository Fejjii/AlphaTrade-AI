"use client";

import { RefreshCw } from "lucide-react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { RiskBadge } from "@/components/RiskBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { PaperModeIndicator } from "@/components/ui/paper-mode-indicator";
import { useAppContext, useMockProviders, useSafetyPosture } from "@/contexts/AppContext";
import { useAuth } from "@/contexts/AuthContext";
import { appConfig } from "@/lib/config";

export function TopBar() {
  const { refreshStatus, loading, killSwitchActive } = useAppContext();
  const { user, organization, logout } = useAuth();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const providers = useMockProviders();
  const mockCount = providers.filter((p) => p.is_mock).length;
  const paperConfirmed = executionMode === "paper" && realTradingEnabled === false;

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
          <PaperModeIndicator active={paperConfirmed} />
          <StatusBadge
            label={(executionMode ?? "unverified").toUpperCase()}
            tone={executionMode === "paper" ? "paper" : "warn"}
          />
          <StatusBadge
            label={
              realTradingEnabled === true
                ? "Real ON"
                : realTradingEnabled === false
                  ? "Real OFF"
                  : "Real ?"
            }
            tone={
              realTradingEnabled === true
                ? "blocked"
                : realTradingEnabled === false
                  ? "success"
                  : "warn"
            }
          />
          <span className="hidden sm:inline-flex">
            <StatusBadge label={`${mockCount} mock`} tone="info" />
          </span>
          <RiskBadge level={killSwitchActive ? "critical" : "low"} />
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
    </header>
  );
}
