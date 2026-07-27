import { PaperPortfolioCharts } from "@/components/portfolio/PaperPortfolioCharts";
import { isValidTimestamp } from "@/components/portfolio/portfolioMetricDisplay";
import type { SourceResult } from "@/components/workflows/sourceResult";
import { Panel, PanelHeader, PanelTitle } from "@/components/ui/panel";
import type { PaperPortfolioResponse } from "@/lib/api/types";

export function PortfolioHistoryPanel({
  portfolio,
}: {
  portfolio: SourceResult<PaperPortfolioResponse> | null | undefined;
}) {
  if (!portfolio) {
    return (
      <section aria-labelledby="portfolio-history-heading" data-testid="portfolio-history-panel">
        <Panel>
          <PanelHeader>
            <PanelTitle id="portfolio-history-heading">Portfolio history</PanelTitle>
          </PanelHeader>
          <p className="text-sm text-text-muted" data-testid="portfolio-history-loading">
            Loading equity and drawdown history…
          </p>
        </Panel>
      </section>
    );
  }

  if (!portfolio.available || !portfolio.data) {
    return (
      <section aria-labelledby="portfolio-history-heading" data-testid="portfolio-history-panel">
        <Panel>
          <PanelHeader>
            <PanelTitle id="portfolio-history-heading">Portfolio history</PanelTitle>
          </PanelHeader>
          <div
            role="alert"
            className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
            data-testid="portfolio-history-unavailable"
          >
            Portfolio history is unavailable.
            {portfolio.error ? ` ${portfolio.error}` : ""} Missing series are not fabricated.
          </div>
        </Panel>
      </section>
    );
  }

  const equity = portfolio.data.equity_curve;
  const daily = portfolio.data.daily_series;
  const validEquityTimestamps = equity.filter((point) => isValidTimestamp(point.timestamp)).length;
  const missingEquityTimestamps = equity.length - validEquityTimestamps;
  const partial =
    equity.length === 0 ||
    daily.length === 0 ||
    missingEquityTimestamps > 0 ||
    portfolio.data.account.limitations.length > 0;

  return (
    <section aria-labelledby="portfolio-history-heading" data-testid="portfolio-history-panel">
      <Panel>
        <PanelHeader>
          <div>
            <PanelTitle id="portfolio-history-heading">Portfolio history</PanelTitle>
            <p className="mt-1 text-sm text-text-muted">
              Equity and drawdown from existing snapshot / daily-series data only.
            </p>
          </div>
        </PanelHeader>

        {partial ? (
          <p className="mb-3 text-sm text-warning" data-testid="portfolio-history-partial">
            Partial history coverage
            {missingEquityTimestamps > 0
              ? ` — ${missingEquityTimestamps} equity point(s) lack valid timestamps`
              : ""}
            {equity.length === 0 ? " — equity curve empty" : ""}
            {daily.length === 0 ? " — daily series empty" : ""}.
          </p>
        ) : (
          <p className="mb-3 text-sm text-text-muted" data-testid="portfolio-history-complete">
            History coverage appears complete for the loaded series.
          </p>
        )}

        <PaperPortfolioCharts equityCurve={equity} dailySeries={daily} />
      </Panel>
    </section>
  );
}
