"use client";

import Link from "next/link";

import { EmailVerificationNotice } from "@/components/account/EmailVerificationNotice";
import { WatcherWatchlistSection } from "@/components/WatcherWatchlistSection";
import { NotificationSettingsPanel } from "@/components/NotificationSettingsPanel";
import { RiskSettingsSummary } from "@/components/settings/RiskSettingsSummary";
import {
  SettingsReadout,
  SettingsUnavailable,
} from "@/components/settings/SettingsReadout";
import { StrategySettingsSummary } from "@/components/settings/StrategySettingsSummary";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { useAppContext, useSafetyPosture } from "@/contexts/AppContext";
import { useWatcherMonitoring } from "@/hooks/useWatcherMonitoring";
import { formatDateTime } from "@/lib/format";
import { formatReasonCode, watcherStatusTone } from "@/lib/watcher-monitoring";

const sections = [
  ["markets", "Markets"],
  ["strategies", "Strategies"],
  ["notifications", "Notifications"],
  ["risk", "Risk"],
  ["account-system", "Account and system"],
] as const;

export default function SettingsPage() {
  const { user, organization } = useAuth();
  const { executionMode, realTradingEnabled, postureKnown } =
    useSafetyPosture();
  const {
    health,
    providers,
    loading: systemLoading,
    refreshStatus,
  } = useAppContext();
  const monitoring = useWatcherMonitoring();
  const snapshot = monitoring.loading ? null : monitoring.data;
  const marketProviders = providers?.providers.filter(
    (provider) => provider.kind === "market_data",
  );
  const telegramRuntime = health?.worker_runtime?.telegram;

  return (
    <div className="space-y-6" data-testid="settings-workspace">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-text-muted">
          Your markets, strategies, alerts, and paper risk parameters.
        </p>
      </div>
      <nav aria-label="Settings sections" className="flex flex-wrap gap-2">
        {sections.map(([id, title]) => (
          <a
            key={id}
            href={`#${id}`}
            className="inline-flex min-h-11 items-center rounded-control border border-border-subtle px-3 py-2 text-sm text-text-secondary hover:bg-surface-2"
          >
            {title}
          </a>
        ))}
      </nav>

      <section
        id="markets"
        aria-labelledby="markets-heading"
        className="scroll-mt-24 space-y-3"
      >
        <h2 id="markets-heading" className="text-lg font-semibold">
          Markets
        </h2>
        <p className="text-sm text-text-muted">
          Choose and order your Watcher markets. Enabled markets still need
          available data and a running Watcher.
        </p>
        <WatcherWatchlistSection />
        <Card>
          <CardContent className="space-y-3 pt-4 lg:pt-6">
            <p className="text-sm text-text-secondary">
              Reported monitoring universe:{" "}
              {snapshot
                ? snapshot.symbols_monitored.join(", ") || "No markets reported"
                : "Unavailable"}
            </p>
            <p className="text-xs text-text-muted">
              The reported universe can include paper-monitoring markets beyond
              your editable watchlist.
            </p>
            <SettingsReadout
              rows={[
                [
                  "Watcher enabled",
                  snapshot
                    ? snapshot.paper_posture.watcher_config_enabled
                      ? "Yes"
                      : "No"
                    : "Unavailable",
                ],
                [
                  "Market data providers",
                  marketProviders?.length
                    ? marketProviders
                        .map(
                          (provider) =>
                            `${provider.name}: ${provider.health}${provider.is_mock ? " (simulated)" : ""}${provider.using_fallback ? " (fallback)" : ""}`,
                        )
                        .join(" · ")
                    : "Unavailable",
                ],
              ]}
            />
          </CardContent>
        </Card>
      </section>

      <section
        id="strategies"
        aria-labelledby="strategies-heading"
        className="scroll-mt-24 space-y-3"
      >
        <h2 id="strategies-heading" className="text-lg font-semibold">
          Strategies
        </h2>
        <StrategySettingsSummary
          snapshot={snapshot}
          loading={monitoring.loading}
          onRetry={() => void monitoring.reload()}
        />
      </section>

      <section
        id="notifications"
        aria-labelledby="notifications-heading"
        className="scroll-mt-24 space-y-3"
      >
        <h2 id="notifications-heading" className="text-lg font-semibold">
          Notifications
        </h2>
        <NotificationSettingsPanel snapshot={snapshot} />
      </section>

      <section
        id="risk"
        aria-labelledby="risk-heading"
        className="scroll-mt-24 space-y-3"
      >
        <h2 id="risk-heading" className="text-lg font-semibold">
          Risk
        </h2>
        <RiskSettingsSummary />
      </section>

      <section
        id="account-system"
        aria-labelledby="account-system-heading"
        className="scroll-mt-24 space-y-3"
      >
        <h2 id="account-system-heading" className="text-lg font-semibold">
          Account and system
        </h2>
        <EmailVerificationNotice />
        <Card>
          <CardHeader>
            <p className="text-sm text-text-muted">Your account</p>
          </CardHeader>
          <CardContent className="space-y-3">
            <SettingsReadout
              rows={[
                ["Email", user?.email ?? "Unavailable"],
                ["Organization", organization?.name ?? "Unavailable"],
                [
                  "Email verified",
                  <span key="verified" data-testid="settings-email-verified">
                    {user
                      ? user.email_verified
                        ? "Yes — verified"
                        : "No — not verified"
                      : "Unavailable"}
                  </span>,
                ],
              ]}
            />
            <div className="flex flex-wrap gap-4 text-sm">
              <Link
                href="/settings/team"
                className="text-emerald-400 hover:underline"
              >
                Manage team invitations
              </Link>
              <Link
                href="/settings/billing"
                className="text-emerald-400 hover:underline"
              >
                Billing &amp; Usage
              </Link>
            </div>
          </CardContent>
        </Card>
        <Card data-testid="settings-runtime-posture">
          <CardHeader>
            <p className="text-sm text-text-muted">Current system status</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <SettingsReadout
              rows={[
                [
                  "Paper mode",
                  <span
                    key="execution"
                    data-testid="settings-posture-execution"
                  >
                    <StatusBadge
                      label={
                        !postureKnown
                          ? "Unverified"
                          : executionMode === "paper" &&
                              realTradingEnabled === false
                            ? "Confirmed"
                            : "Paper-only mode not confirmed"
                      }
                      tone={
                        !postureKnown
                          ? "muted"
                          : executionMode === "paper" &&
                              realTradingEnabled === false
                            ? "paper"
                            : "blocked"
                      }
                    />
                  </span>,
                ],
                [
                  "Real trading",
                  <span
                    key="trading"
                    data-testid="settings-posture-real-trading"
                  >
                    {realTradingEnabled === null
                      ? "Unverified"
                      : realTradingEnabled
                        ? "Enabled — check system configuration"
                        : "Disabled"}
                  </span>,
                ],
                [
                  "Watcher status",
                  snapshot ? (
                    <StatusBadge
                      label={formatReasonCode(
                        snapshot.watcher_status.toLowerCase(),
                      )}
                      tone={watcherStatusTone(snapshot.watcher_status)}
                    />
                  ) : (
                    "Unavailable"
                  ),
                ],
                [
                  "Data freshness at last snapshot",
                  snapshot
                    ? formatReasonCode(snapshot.market_freshness.status)
                    : "Unavailable",
                ],
                [
                  "Market data observed",
                  snapshot?.market_freshness.observed_at
                    ? formatDateTime(snapshot.market_freshness.observed_at)
                    : "Unavailable",
                ],
                [
                  "Last Watcher scan",
                  snapshot
                    ? snapshot.last_scan_at
                      ? formatDateTime(snapshot.last_scan_at)
                      : "No scan reported"
                    : "Unavailable",
                ],
                [
                  "Telegram runtime",
                  telegramRuntime?.available === true
                    ? formatReasonCode(
                        (
                          telegramRuntime.health_state ?? "unverified"
                        ).toLowerCase(),
                      )
                    : "Unavailable",
                ],
                [
                  "Telegram connection",
                  "Unverified — see delivery configuration under Notifications",
                ],
                [
                  "Telegram network permission",
                  health?.telegram_network_permitted === undefined
                    ? "Unverified"
                    : health.telegram_network_permitted
                      ? "Permitted by system"
                      : "Disabled by system",
                ],
              ]}
            />
            <p className="text-xs text-text-muted">
              Status comes from the backend. Configuration being enabled does
              not confirm monitoring or delivery is running.
            </p>
            {snapshot ? (
              <p className="text-xs text-text-muted">
                Monitoring snapshot: {formatDateTime(snapshot.generated_at)}
              </p>
            ) : (
              <SettingsUnavailable
                label="Watcher status"
                loading={monitoring.loading}
                onRetry={() => void monitoring.reload()}
              />
            )}
            <div className="space-y-2" data-testid="settings-provider-health">
              <p className="text-sm font-medium">Provider health</p>
              {providers?.providers.length ? (
                <ul className="space-y-1 text-sm text-text-secondary">
                  {providers.providers.map((provider) => (
                    <li
                      key={`${provider.kind}-${provider.name}`}
                      className="break-words"
                    >
                      {provider.name}: {provider.health}
                      {provider.is_mock ? " · Simulated" : ""}
                      {provider.using_fallback ? " · Fallback" : ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <SettingsUnavailable
                  label="Provider health"
                  loading={systemLoading}
                />
              )}
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={systemLoading || monitoring.loading}
              onClick={() => {
                void refreshStatus();
                void monitoring.reload();
              }}
            >
              Refresh system status
            </Button>
          </CardContent>
        </Card>
      </section>

      <aside
        className="space-y-2 border-t border-border-subtle pt-4 text-sm"
        data-testid="settings-advanced-link"
      >
        <Link
          href="/settings/advanced"
          className="text-emerald-400 hover:underline"
        >
          Advanced settings
        </Link>
        <p className="text-xs text-text-muted">
          Diagnostics, infrastructure, audit, and validation tools.
        </p>
      </aside>
    </div>
  );
}
