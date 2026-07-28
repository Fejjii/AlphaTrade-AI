"use client";

import { EmailVerificationNotice } from "@/components/account/EmailVerificationNotice";
import { NotificationSettingsPanel } from "@/components/NotificationSettingsPanel";
import { PaperModeBanner } from "@/components/PaperModeBanner";
import { SafetyDisclaimers } from "@/components/SafetyDisclaimers";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { useSafetyPosture } from "@/contexts/AppContext";
import Link from "next/link";
import { appConfig } from "@/lib/config";

export default function SettingsPage() {
  const { user, organization } = useAuth();
  const { executionMode, realTradingEnabled, postureKnown } = useSafetyPosture();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-zinc-400">Environment and safety configuration for this workspace.</p>
      </div>
      <PaperModeBanner />
      <EmailVerificationNotice />
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm text-zinc-300 md:grid-cols-2">
          <span>Email: {user?.email ?? "—"}</span>
          <span>
            Email verified:{" "}
            {user?.email_verified ? (
              <span className="text-emerald-400">Yes</span>
            ) : (
              <span className="text-amber-400">No</span>
            )}
          </span>
          <span>
            <Link href="/settings/team" className="text-emerald-400 hover:underline">
              Manage team invitations
            </Link>
          </span>
          <span>
            <Link href="/settings/billing" className="text-emerald-400 hover:underline">
              Billing &amp; plans
            </Link>
          </span>
        </CardContent>
      </Card>
      <Card data-testid="settings-runtime-posture">
        <CardHeader>
          <CardTitle>Verified runtime posture</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-zinc-300">
          <div className="flex flex-wrap items-center gap-2">
            <span data-testid="settings-posture-execution">
              <StatusBadge
                label={
                  postureKnown && executionMode != null
                    ? `Execution: ${executionMode.toUpperCase()}`
                    : "Execution: unverified"
                }
                tone={
                  postureKnown && executionMode === "paper"
                    ? "paper"
                    : postureKnown
                      ? "warn"
                      : "muted"
                }
              />
            </span>
            <span data-testid="settings-posture-real-trading">
              <StatusBadge
                label={
                  realTradingEnabled === true
                    ? "Real trading: enabled"
                    : realTradingEnabled === false
                      ? "Real trading: disabled"
                      : "Real trading: unverified"
                }
                tone={
                  realTradingEnabled === true
                    ? "blocked"
                    : realTradingEnabled === false
                      ? "success"
                      : "muted"
                }
              />
            </span>
          </div>
          <p className="text-xs text-zinc-500">
            {postureKnown
              ? "Reported live by the backend /health endpoint."
              : "Waiting for backend health status — posture is confirmed only from the live backend, never from build configuration."}
          </p>
        </CardContent>
      </Card>
      <Card data-testid="settings-build-config">
        <CardHeader>
          <CardTitle>Build configuration (not runtime-verified)</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm text-zinc-300 md:grid-cols-2">
          <span>API URL: {appConfig.apiBaseUrl}</span>
          <span>Signed in as: {user?.email ?? "—"}</span>
          <span>Organization: {organization?.name ?? "—"}</span>
          <span>Execution mode (build config): {appConfig.executionMode}</span>
          <span>Provider mode (build config): {appConfig.providerMode}</span>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Provider status snapshot</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-400">
          Live provider cards load from the backend on other pages. Configure env vars in
          <code className="mx-1 rounded bg-zinc-900 px-1">frontend/.env.local</code>.
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Safety &amp; disclaimers</CardTitle>
        </CardHeader>
        <CardContent>
          <SafetyDisclaimers />
        </CardContent>
      </Card>
      <NotificationSettingsPanel />
    </div>
  );
}
