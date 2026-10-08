"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { manualDemo } from "@/lib/api/manual-demo";

export function ManualDemoActivity({ refreshKey }: { refreshKey?: string }) {
  const [offset, setOffset] = useState(0);
  const load = useCallback(
    () => manualDemo.history({ limit: 5, offset }),
    [offset],
  );
  const { data, loading, error, reload } = useAsyncData(load, [
    offset,
    refreshKey,
  ]);
  return (
    <section
      aria-label="Recent manual demo activity"
      className="space-y-2 border-t border-border-subtle pt-3"
    >
      <h3>Recent manual demo activity</h3>
      <p className="text-sm text-text-muted">
        Every recorded attempt has a permanent detail link. Blocked attempts are
        separate from submitted orders and actual fills.
      </p>
      <Button disabled={loading} onClick={() => void reload()}>
        Refresh attempt history
      </Button>
      {loading && <p>Loading recorded attempts…</p>}
      {error && <p role="alert">Attempt history unavailable: {error}</p>}
      {data && (
        <>
          {!data.items.length && (
            <p>No recorded manual demo attempts in this account scope.</p>
          )}
          <ul className="space-y-2">
            {data.items.map((item) => (
              <li key={item.command_id}>
                <Link
                  className="underline"
                  href={`/execution/manual-demo/${encodeURIComponent(item.command_id)}`}
                >
                  {item.symbol} {item.side === "BUY" ? "long" : "short"} ·{" "}
                  {item.requested_contracts} contracts ({item.base_quantity}{" "}
                  BTC) ·{" "}
                  {item.evidence.execution_status?.replaceAll("_", " ") ??
                    item.evidence.status}
                </Link>
                <p className="text-sm">
                  {new Date(
                    item.submitted_at ?? item.attempted_at,
                  ).toLocaleString()}{" "}
                  · {item.account_name} · recorded fills{" "}
                  {item.evidence.filled_quantity} contracts
                </p>
                {item.blocked_reason && (
                  <p className="text-sm">
                    Blocked: {item.blocked_reason.replaceAll("_", " ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
          {offset > 0 && (
            <Button
              disabled={loading}
              onClick={() => setOffset(Math.max(0, offset - 5))}
            >
              Newer attempts
            </Button>
          )}
          {offset + data.items.length < data.total && (
            <Button disabled={loading} onClick={() => setOffset(offset + 5)}>
              Older attempts
            </Button>
          )}
        </>
      )}
    </section>
  );
}
