import Link from "next/link";

import type { ClosedPositionsView } from "@/components/portfolio/buildClosedPositionRows";
import {
  formatMetricValue,
  formatOptionalTimestamp,
  pnlTone,
} from "@/components/portfolio/portfolioMetricDisplay";
import { StatusBadge } from "@/components/StatusBadge";
import { DataNumber } from "@/components/ui/data-number";
import { Panel, PanelHeader, PanelTitle } from "@/components/ui/panel";

function journalTone(
  status: string,
): "healthy" | "warn" | "muted" | "info" {
  switch (status) {
    case "journaled":
      return "healthy";
    case "not_journaled":
      return "warn";
    case "unverified":
      return "info";
    default:
      return "muted";
  }
}

export function ClosedPositionsPanel({ view }: { view: ClosedPositionsView }) {
  return (
    <section
      aria-labelledby="closed-positions-heading"
      data-testid="closed-positions-panel"
      className="space-y-3"
    >
      <Panel>
        <PanelHeader>
          <div>
            <PanelTitle id="closed-positions-heading">Recent closed positions</PanelTitle>
            <p className="mt-1 text-sm text-text-muted">
              Recent closed paper trades with realised result and verifiable journal status only.
            </p>
          </div>
        </PanelHeader>

        {view.status === "loading" ? (
          <p className="text-sm text-text-muted" data-testid="closed-positions-loading">
            Loading closed paper positions…
          </p>
        ) : null}

        {view.status === "unavailable" ? (
          <div
            role="alert"
            className="rounded-control border border-danger-border bg-danger-muted/40 px-3 py-2 text-sm text-danger"
            data-testid="closed-positions-unavailable"
          >
            {view.reasonUnavailable}
          </div>
        ) : null}

        {view.status === "empty" ? (
          <p className="text-sm text-text-secondary" data-testid="closed-positions-empty">
            No closed paper positions in complete coverage.
          </p>
        ) : null}

        {view.coverageMessage ? (
          <p className="text-sm text-warning" data-testid="closed-positions-coverage">
            {view.coverageMessage}
          </p>
        ) : null}

        {view.rows && view.rows.length > 0 ? (
          <ul className="grid gap-3 md:hidden" data-testid="closed-positions-mobile">
            {view.rows.map((row) => {
              const realized = formatMetricValue(row.realizedPnl);
              return (
                <li
                  key={row.position.id}
                  className="rounded-control border border-border-subtle bg-surface-1 px-3 py-3"
                  data-testid={`closed-position-${row.position.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-text-primary">
                      {row.position.symbol} · {row.position.direction.toUpperCase()}
                    </h3>
                    <div className="flex flex-wrap items-center gap-2">
                      <span data-testid={`closed-position-status-${row.position.id}`}>
                        <StatusBadge
                          label={row.position.status}
                          tone={row.position.status === "liquidated" ? "warn" : "muted"}
                        />
                      </span>
                      <StatusBadge
                        label={row.journalStatusLabel}
                        tone={journalTone(row.journalStatus)}
                      />
                    </div>
                  </div>
                  <dl className="mt-3 grid gap-2 text-sm">
                    <div>
                      <dt className="text-xs text-text-muted">Status</dt>
                      <dd className="capitalize">{row.position.status}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">Realised result</dt>
                      <dd>
                        {realized.kind === "value" ? (
                          <DataNumber
                            value={realized.text}
                            numeric={realized.numeric}
                            tone={pnlTone(realized.numeric)}
                            signed
                          />
                        ) : (
                          <span data-testid={`closed-position-pnl-unavailable-${row.position.id}`}>
                            Unavailable
                          </span>
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">Close timestamp</dt>
                      <dd>{formatOptionalTimestamp(row.closedAt)}</dd>
                    </div>
                  </dl>
                  {row.journalHref ? (
                    <Link
                      href={row.journalHref}
                      className="mt-3 inline-block text-sm underline text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                      data-testid={`closed-position-journal-link-${row.position.id}`}
                    >
                      {row.journalStatus === "journaled" ? "Open journal entry" : "Journal this trade"}
                    </Link>
                  ) : (
                    <p
                      className="mt-3 text-sm text-text-muted"
                      data-testid={`closed-position-journal-missing-${row.position.id}`}
                    >
                      Journal relationship unavailable
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        ) : null}

        {view.rows && view.rows.length > 0 ? (
          <div className="hidden overflow-x-auto md:block" data-testid="closed-positions-desktop">
            <table className="w-full min-w-0 text-left text-sm">
              <thead>
                <tr className="border-b border-border-subtle text-text-muted">
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Symbol
                  </th>
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Direction
                  </th>
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Status
                  </th>
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Realised result
                  </th>
                  <th scope="col" className="py-2 pr-3 font-medium">
                    Closed
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    Journal
                  </th>
                </tr>
              </thead>
              <tbody>
                {view.rows.map((row) => {
                  const realized = formatMetricValue(row.realizedPnl);
                  return (
                    <tr
                      key={`desk-${row.position.id}`}
                      className="border-b border-border-subtle/60"
                      data-testid={`closed-position-row-${row.position.id}`}
                    >
                      <td className="py-2 pr-3 text-text-primary">{row.position.symbol}</td>
                      <td className="py-2 pr-3 uppercase">{row.position.direction}</td>
                      <td
                        className="py-2 pr-3 capitalize"
                        data-testid={`closed-position-status-row-${row.position.id}`}
                      >
                        {row.position.status}
                      </td>
                      <td className="py-2 pr-3">
                        {realized.kind === "value" ? (
                          <DataNumber
                            value={realized.text}
                            numeric={realized.numeric}
                            tone={pnlTone(realized.numeric)}
                            signed
                          />
                        ) : (
                          "Unavailable"
                        )}
                      </td>
                      <td className="py-2 pr-3">{formatOptionalTimestamp(row.closedAt)}</td>
                      <td className="py-2">
                        {row.journalHref ? (
                          <Link
                            href={row.journalHref}
                            className="underline text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                          >
                            {row.journalStatusLabel}
                          </Link>
                        ) : (
                          row.journalStatusLabel
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </section>
  );
}
