import Link from "next/link";

import {
  formatMetricValue,
  formatOptionalTimestamp,
  pnlTone,
} from "@/components/portfolio/portfolioMetricDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import { DataNumber } from "@/components/ui/data-number";
import { Panel, PanelHeader, PanelTitle } from "@/components/ui/panel";
import type { DailyDisciplineSnapshot, PaperPortfolioResponse } from "@/lib/api/types";
import { humanizeLimitation } from "@/lib/format";

export type DailyPnlDisplay = {
  value: string | null;
  source: "discipline_today" | "daily_series_range" | "none";
  label: string;
};

type AccountOverviewPanelProps = {
  portfolio: SourceResult<PaperPortfolioResponse> | null | undefined;
  paperConfirmed: boolean;
  discipline: SourceResult<DailyDisciplineSnapshot | null> | null | undefined;
};

function MetricCell({
  testId,
  label,
  value,
  signed = false,
}: {
  testId: string;
  label: string;
  value: string | number | null | undefined;
  signed?: boolean;
}) {
  const display = formatMetricValue(value);
  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-1 px-3 py-3"
      data-testid={testId}
    >
      <p className="text-xs text-text-muted">{label}</p>
      {display.kind === "value" ? (
        <DataNumber
          className="mt-1 text-lg font-semibold"
          value={display.text}
          numeric={display.numeric}
          tone={signed ? pnlTone(display.numeric) : "default"}
          signed={signed}
        />
      ) : (
        <p className="mt-1 text-sm text-text-muted" data-testid={`${testId}-unavailable`}>
          {display.text}
        </p>
      )}
    </div>
  );
}

export function resolveDailyPnlDisplay(
  discipline: SourceResult<DailyDisciplineSnapshot | null> | null | undefined,
  latestDailyPnl: string | null | undefined,
): DailyPnlDisplay {
  if (discipline?.available && discipline.data?.net_pnl_today_paper != null) {
    return {
      value: discipline.data.net_pnl_today_paper,
      source: "discipline_today",
      label: "Today's paper P&L",
    };
  }
  if (latestDailyPnl != null && latestDailyPnl !== "") {
    return {
      value: latestDailyPnl,
      source: "daily_series_range",
      label: "Latest daily P&L in selected range",
    };
  }
  return {
    value: null,
    source: "none",
    label: "Daily P&L",
  };
}

export function AccountOverviewPanel({
  portfolio,
  paperConfirmed,
  discipline,
}: AccountOverviewPanelProps) {
  if (!portfolio) {
    return (
      <section aria-labelledby="account-overview-heading" data-testid="account-overview-panel">
        <Panel>
          <PanelHeader>
            <PanelTitle id="account-overview-heading">Account overview</PanelTitle>
          </PanelHeader>
          <p className="text-sm text-text-muted" data-testid="account-overview-loading">
            Loading simulated account overview…
          </p>
        </Panel>
      </section>
    );
  }

  if (!portfolio.available || !portfolio.data) {
    return (
      <section aria-labelledby="account-overview-heading" data-testid="account-overview-panel">
        <Panel>
          <PanelHeader>
            <PanelTitle id="account-overview-heading">Account overview</PanelTitle>
          </PanelHeader>
          <div
            role="alert"
            className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
            data-testid="account-overview-unavailable"
          >
            Simulated account metrics are unavailable.
            {portfolio.error ? ` ${portfolio.error}` : ""} Balances and P&amp;L are not shown as
            zero.
          </div>
        </Panel>
      </section>
    );
  }

  const account = portfolio.data.account;
  const metrics = portfolio.data.metrics;
  const latestDaily = portfolio.data.daily_series.at(-1);
  const dailyPnl = resolveDailyPnlDisplay(discipline, latestDaily?.daily_pnl);
  const latestDailyDrawdown = latestDaily?.daily_drawdown ?? null;

  return (
    <section aria-labelledby="account-overview-heading" data-testid="account-overview-panel">
      <Panel>
        <PanelHeader>
          <div>
            <PanelTitle id="account-overview-heading">Account overview</PanelTitle>
            <p className="mt-1 text-sm text-text-muted">
              {paperConfirmed
                ? "Confirmed simulated / paper account metrics from stored portfolio data."
                : "Simulated account wording is limited until paper posture is confirmed."}
            </p>
          </div>
        </PanelHeader>

        <div className="mb-3 flex flex-wrap gap-3 text-xs text-text-muted">
          <span data-testid="portfolio-snapshot-time">
            Latest snapshot: {formatOptionalTimestamp(account.as_of)}
          </span>
          <span data-testid="portfolio-account-mode">
            {paperConfirmed ? "Simulated paper account" : "Paper mode not confirmed"}
          </span>
        </div>

        <div
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          data-testid="paper-portfolio-summary-cards"
        >
          <MetricCell
            testId="portfolio-current-equity"
            label="Current simulated equity"
            value={account.current_equity}
          />
          <MetricCell
            testId="portfolio-starting-balance"
            label="Starting / reference equity"
            value={account.starting_balance}
          />
          <MetricCell
            testId="portfolio-realized-pnl"
            label="Realised P&L"
            value={account.cumulative_realized_pnl}
            signed
          />
          <MetricCell
            testId="portfolio-unrealized-pnl"
            label="Unrealised P&L"
            value={account.unrealized_pnl}
            signed
          />
          <MetricCell
            testId="portfolio-latest-daily-drawdown"
            label="Latest daily drawdown in selected range"
            value={latestDailyDrawdown}
          />
          <MetricCell
            testId="portfolio-daily-pnl"
            label={dailyPnl.label}
            value={dailyPnl.value}
            signed
          />
          <MetricCell
            testId="portfolio-max-drawdown"
            label="Max drawdown"
            value={metrics.max_drawdown}
          />
          <MetricCell
            testId="portfolio-trade-count"
            label="Closed trades (account)"
            value={account.closed_trade_count}
          />
        </div>

        <p className="mt-2 text-caption text-text-muted" data-testid="portfolio-daily-pnl-source">
          Daily P&amp;L source:{" "}
          {dailyPnl.source === "discipline_today"
            ? "today's paper discipline snapshot"
            : dailyPnl.source === "daily_series_range"
              ? "latest daily series point in selected range (not claimed as today)"
              : "unavailable"}
        </p>

        {account.limitations.length > 0 ? (
          <ul
            className="mt-3 list-disc space-y-1 pl-5 text-xs text-warning"
            data-testid="account-overview-limitations"
          >
            {account.limitations.map((item) => (
              <li key={item}>{humanizeLimitation(item)}</li>
            ))}
          </ul>
        ) : null}

        <p className="mt-3 text-xs text-text-muted">
          Values use the units returned by the backend. No currency conversion is applied.{" "}
          <Link href="/risk" className="underline">
            Open risk settings
          </Link>
        </p>
      </Panel>
    </section>
  );
}
