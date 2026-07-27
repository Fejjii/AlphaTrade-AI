import Link from "next/link";

import type { OpenPositionsView } from "@/components/portfolio/buildOpenPositionRows";
import {
  formatMetricValue,
  formatOptionalTimestamp,
  pnlTone,
} from "@/components/portfolio/portfolioMetricDisplay";
import { StatusBadge } from "@/components/StatusBadge";
import { DataNumber } from "@/components/ui/data-number";
import { Panel, PanelHeader, PanelTitle } from "@/components/ui/panel";

export function OpenPositionsPanel({ view }: { view: OpenPositionsView }) {
  return (
    <section
      aria-labelledby="open-positions-heading"
      data-testid="open-positions-panel"
      className="space-y-3"
    >
      <Panel>
        <PanelHeader>
          <div>
            <PanelTitle id="open-positions-heading">Exposure and open positions</PanelTitle>
            <p className="mt-1 text-sm text-text-muted">
              Open paper positions only. Mobile uses stacked cards; wide tables are not forced.
            </p>
          </div>
        </PanelHeader>

        {view.status === "loading" ? (
          <p className="text-sm text-text-muted" data-testid="open-positions-loading">
            Loading open paper positions…
          </p>
        ) : null}

        {view.status === "unavailable" ? (
          <div
            role="alert"
            className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
            data-testid="open-positions-unavailable"
          >
            {view.reasonUnavailable}
          </div>
        ) : null}

        {view.status === "empty" ? (
          <p className="text-sm text-text-secondary" data-testid="open-positions-empty">
            No open paper positions (complete coverage confirmed).
          </p>
        ) : null}

        {view.coverageMessage ? (
          <p className="text-sm text-warning" data-testid="open-positions-coverage">
            {view.coverageMessage}
          </p>
        ) : null}

        {view.rows && view.rows.length > 0 ? (
          <ul className="grid gap-3" data-testid="open-positions-list">
            {view.rows.map((row) => {
              const unrealized = formatMetricValue(row.unrealizedPnl);
              const size = formatMetricValue(row.size);
              const leverage = formatMetricValue(row.leverage);
              const entry = formatMetricValue(row.entry);
              return (
                <li
                  key={row.position.id}
                  className="rounded-control border border-border-subtle bg-surface-1 px-3 py-3"
                  data-testid={`open-position-${row.position.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-text-primary">
                      {row.position.symbol} · {row.position.direction.toUpperCase()}
                    </h3>
                    <StatusBadge label={row.position.status} tone="ok" />
                  </div>
                  <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-text-muted">Position size</dt>
                      <dd>
                        {size.kind === "value" ? size.text : "Unavailable"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">Leverage</dt>
                      <dd>{leverage.kind === "value" ? leverage.text : "Unavailable"}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">Entry</dt>
                      <dd>{entry.kind === "value" ? entry.text : "Unavailable"}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">Mark / current price</dt>
                      <dd data-testid={`open-position-mark-${row.position.id}`}>
                        {row.markPrice != null
                          ? formatMetricValue(row.markPrice).kind === "value"
                            ? formatMetricValue(row.markPrice).text
                            : "Unavailable"
                          : "Not returned by API"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">Unrealised P&amp;L</dt>
                      <dd>
                        {unrealized.kind === "value" ? (
                          <DataNumber
                            value={unrealized.text}
                            numeric={unrealized.numeric}
                            tone={pnlTone(unrealized.numeric)}
                            signed
                          />
                        ) : (
                          "Unavailable"
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">Opened</dt>
                      <dd>{formatOptionalTimestamp(row.position.opened_at)}</dd>
                    </div>
                  </dl>
                  <div className="mt-3 flex flex-wrap gap-3 text-sm">
                    <Link
                      href={row.relationships.positionDetailHref}
                      className="underline text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                      data-testid={`open-position-positions-link-${row.position.id}`}
                    >
                      View positions
                    </Link>
                    {row.relationships.strategyHref ? (
                      <Link
                        href={row.relationships.strategyHref}
                        className="underline text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                        data-testid={`open-position-strategy-link-${row.position.id}`}
                      >
                        Related strategy
                        {row.relationships.strategyName
                          ? ` (${row.relationships.strategyName})`
                          : ""}
                      </Link>
                    ) : (
                      <span
                        className="text-text-muted"
                        data-testid={`open-position-strategy-missing-${row.position.id}`}
                      >
                        No related strategy identifier
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : null}
      </Panel>
    </section>
  );
}
