import { PaperPortfolioCharts } from "@/components/portfolio/PaperPortfolioCharts";
import { assessPortfolioHistoryCoverage } from "@/components/portfolio/portfolioHistoryCoverage";
import type { SourceResult } from "@/components/workflows/sourceResult";
import { Panel, PanelHeader, PanelTitle } from "@/components/ui/panel";
import type { PaperPortfolioResponse } from "@/lib/api/types";
import { humanizeLimitation } from "@/lib/format";

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
  const coverage = assessPortfolioHistoryCoverage(portfolio.data);

  return (
    <section aria-labelledby="portfolio-history-heading" data-testid="portfolio-history-panel">
      <Panel>
        <PanelHeader>
          <div>
            <PanelTitle id="portfolio-history-heading">Portfolio history</PanelTitle>
            <p className="mt-1 text-sm text-text-muted">
              Equity and drawdown from existing snapshot / daily-series data only. Empty series are
              confirmed empty, not truncated API coverage.
            </p>
          </div>
        </PanelHeader>

        {coverage.kind === "partial_timestamps" ? (
          <p className="mb-3 text-sm text-warning" data-testid="portfolio-history-partial">
            {coverage.message}
          </p>
        ) : null}

        {coverage.kind === "empty" ? (
          <p className="mb-3 text-sm text-text-muted" data-testid="portfolio-history-empty">
            {coverage.message}
          </p>
        ) : null}

        {coverage.kind === "complete" ? (
          <p className="mb-3 text-sm text-text-muted" data-testid="portfolio-history-complete">
            {coverage.message}
          </p>
        ) : null}

        {coverage.limitations.length > 0 ? (
          <div
            className="mb-3 rounded-control border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-secondary"
            data-testid="portfolio-history-limitations"
          >
            <p className="font-medium text-text-primary">Backend limitations</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {coverage.limitations.map((item) => (
                <li key={item}>{humanizeLimitation(item)}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <PaperPortfolioCharts equityCurve={equity} dailySeries={daily} />
      </Panel>
    </section>
  );
}
