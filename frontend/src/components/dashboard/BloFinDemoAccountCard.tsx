"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDemoAccountSnapshot } from "./useDemoAccountSnapshot";
import { formatCount, formatDateTime, formatPrice } from "@/lib/format";

const statusLabel = {
  ok: "Fresh snapshot",
  degraded: "Degraded snapshot",
  stale: "Stale snapshot",
  unavailable: "Account unavailable",
  not_synced: "No snapshot yet",
  inactive: "Not configured",
};

export function BloFinDemoAccountCard({
  refreshKey = 0,
}: {
  refreshKey?: number;
}) {
  const { account, busy, error, status, hasData, load } =
    useDemoAccountSnapshot(refreshKey);

  return (
    <Card data-testid="dashboard-demo-account">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <CardTitle>BloFin demo account</CardTitle>
          <div className="flex flex-wrap gap-2">
            <Badge variant="info">BLOFIN_DEMO</Badge>
            <Badge variant={status === "ok" ? "success" : "warning"}>
              {status
                ? statusLabel[status]
                : error
                  ? "Account unavailable"
                  : "Loading snapshot…"}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/settings/exchange" className="text-sm text-accent">
            Exchange settings
          </Link>
          {account?.can_refresh ? (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void load(true)}
            >
              {busy ? "Refreshing…" : "Refresh demo account"}
            </Button>
          ) : error ? (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void load()}
            >
              Retry account
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-text-secondary">
          Configured demo venue account · balances and native open positions.
          {account?.can_refresh
            ? " Native data refreshes every 3 minutes while visible; retries slow down after failures."
            : " Saved snapshots reload every 3 minutes while visible."}
          Paper portfolio and performance metrics below have their own scope.
        </p>
        {busy ? (
          <p role="status" className="text-sm text-text-secondary">
            Loading demo account snapshot…
            {account ? " Showing the previous saved snapshot." : ""}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {account ? (
          <>
            <p
              role="status"
              className={
                status === "stale"
                  ? "text-sm text-warning"
                  : "text-sm text-text-secondary"
              }
            >
              {status === "stale"
                ? "Saved demo account snapshot is stale. Refresh for current balances and positions."
                : account.message}
            </p>
            {account.synced_at ? (
              <p className="text-xs text-text-secondary">
                As of {formatDateTime(account.synced_at)}
              </p>
            ) : null}
            {account.last_attempt_at ? (
              <p className="text-xs text-text-secondary">
                Last refresh attempt {formatDateTime(account.last_attempt_at)}
              </p>
            ) : null}
            {!account.can_refresh && account.status !== "inactive" ? (
              <p className="text-xs text-text-secondary">
                An organization owner can refresh the demo account.
              </p>
            ) : null}
            {hasData ? (
              <>
                <dl className="rounded-control border border-border-subtle p-3 text-sm">
                  <dt className="font-medium text-text-primary">Native account equity (USD)</dt>
                  <dd className="mt-2 break-words text-text-secondary">
                    {account.total_equity_usd ?? "—"} USD
                  </dd>
                </dl>
                <div className="grid gap-3 sm:grid-cols-2">
                  {account.balances.map((balance) => (
                    <dl
                      key={balance.asset}
                      className="rounded-control border border-border-subtle p-3 text-sm"
                    >
                      <dt className="font-medium text-text-primary">
                        {balance.asset} balance
                      </dt>
                      <dd className="mt-2 break-words text-text-secondary">
                        Cash balance: {balance.total} {balance.asset}
                      </dd>
                      <dd className="break-words text-text-secondary">
                        Available: {balance.available} {balance.asset}
                      </dd>
                      <dd className="break-words text-text-secondary">
                        Equity: {balance.equity ?? "—"} {balance.asset}
                      </dd>
                    </dl>
                  ))}
                </div>
                {!account.balances.length ? (
                  <p className="text-sm text-text-secondary">
                    No balances reported.
                  </p>
                ) : null}
                {account.balances_truncated ? (
                  <p className="text-xs text-warning">
                    Balance list is incomplete.
                  </p>
                ) : null}
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-text-primary">
                    Native open positions ·{" "}
                    {account.positions_truncated
                      ? `at least ${account.positions.length}`
                      : formatCount(account.position_count)}
                  </h3>
                  {account.positions.map((position, index) => (
                    <div
                      key={`${position.symbol}-${position.side}-${index}`}
                      className="rounded-control border border-border-subtle p-3 text-sm"
                    >
                      <p className="font-medium text-text-primary">
                        {position.symbol} · {position.side}
                      </p>
                      <p className="mt-1 text-text-secondary">
                        {position.contracts} contracts · Leverage{" "}
                        {position.leverage ?? "—"}x
                      </p>
                      <p className="break-words text-text-secondary">
                        Base quantity: {position.base_quantity ?? "—"} {position.base_asset ?? "(unverified instrument metadata)"}
                      </p>
                      <p className="text-text-secondary">
                        Entry {formatPrice(position.entry_price)} · Mark{" "}
                        {formatPrice(position.mark_price)}
                      </p>
                      <p className="break-words text-text-secondary">
                        Unrealized PnL {position.unrealized_pnl ?? "—"} ·
                        instrument currency
                      </p>
                    </div>
                  ))}
                  {!account.positions.length && !account.positions_truncated ? (
                    <p className="text-sm text-text-secondary">
                      No native open positions at this snapshot.
                    </p>
                  ) : null}
                  {account.positions_truncated ? (
                    <p className="text-xs text-warning">
                      Position list is incomplete; a full account count is
                      unavailable.
                    </p>
                  ) : null}
                </div>
              </>
            ) : null}
            <p className="text-xs text-text-secondary">
              Account refresh reads balances and positions. Order fills, SL/TP
              verification and Journal evidence are reviewed separately.
            </p>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
