"use client";

import { RefreshCw } from "lucide-react";

import { KillSwitchButton } from "@/components/KillSwitchButton";
import { RiskBadge } from "@/components/RiskBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { useAppContext, useMockProviders, useSafetyPosture } from "@/contexts/AppContext";
import { useAuth } from "@/contexts/AuthContext";
import { appConfig } from "@/lib/config";

export function TopBar() {
  const { refreshStatus, loading, killSwitchActive } = useAppContext();
  const { user, organization, logout } = useAuth();
  const { executionMode, realTradingEnabled } = useSafetyPosture();
  const providers = useMockProviders();
  const mockCount = providers.filter((p) => p.is_mock).length;

  return (
    <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 lg:gap-3 lg:px-6">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-100">{appConfig.appName}</p>
          <p className="truncate text-xs text-zinc-500">
            {user?.email ?? "Signed in"} · {organization?.name ?? "Tenant"}
          </p>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-1.5 sm:gap-2">
          <StatusBadge label={`${executionMode.toUpperCase()}`} tone="paper" />
          <StatusBadge
            label={realTradingEnabled ? "Real ON" : "Real OFF"}
            tone={realTradingEnabled ? "blocked" : "success"}
          />
          <span className="hidden sm:inline-flex">
            <StatusBadge label={`${mockCount} mock`} tone="info" />
          </span>
          <RiskBadge level={killSwitchActive ? "critical" : "low"} />
          <Button variant="ghost" size="icon" onClick={() => void refreshStatus()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void logout()}>
            Log out
          </Button>
          <KillSwitchButton compact />
        </div>
      </div>
    </header>
  );
}
