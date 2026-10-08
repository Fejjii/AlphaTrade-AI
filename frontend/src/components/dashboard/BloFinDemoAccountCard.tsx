"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  demoAccountApi,
  type DashboardDemoAccount,
} from "@/lib/api/dashboard-demo-account";
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
  const [account, setAccount] = useState<DashboardDemoAccount | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const generation = useRef(0);
  const syncing = useRef(false);

  const load = useCallback(async (refresh = false) => {
    // Dashboard reads cannot overtake or duplicate an explicit venue refresh.
    if (syncing.current) return;
    syncing.current = refresh;
    const request = ++generation.current;
    setBusy(true);
    setError(null);
    try {
      const result = await (refresh
        ? demoAccountApi.refresh()
        : demoAccountApi.latest());
      if (request === generation.current) {
        setAccount(result);
        setNow(Date.now());
      }
    } catch {
      if (request === generation.current) {
        setAccount(null);
        setError(
          "Demo account data could not be loaded. Retry or check Exchange settings.",
        );
      }
    } finally {
      if (refresh) syncing.current = false;
      if (request === generation.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    return () => {
      generation.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!account?.expires_at) return;
    const expires = Date.parse(account.expires_at);
    if (!Number.isFinite(expires)) return;
    const timer = window.setTimeout(
      () => setNow(Date.now()),
      Math.max(0, expires - Date.now()),
    );
    return () => window.clearTimeout(timer);
  }, [account?.expires_at]);

  const expired =
    !!account?.expires_at && now >= Date.parse(account.expires_at);
  const status =
    account && expired && ["ok", "degraded"].includes(account.status)
      ? "stale"
      : account?.status;
  const hasData =
    account && ["ok", "degraded", "stale"].includes(account.status);

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
            {!account.can_refresh && account.status !== "inactive" ? (
              <p className="text-xs text-text-secondary">
                An organization owner can refresh the demo account.
              </p>
            ) : null}
            {hasData ? (
              <>
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
                        Total: {balance.total} {balance.asset}
                      </dd>
                      <dd className="break-words text-text-secondary">
                        Available: {balance.available} {balance.asset}
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
