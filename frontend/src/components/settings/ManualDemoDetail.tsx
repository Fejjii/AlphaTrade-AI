"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import { manualDemo } from "@/lib/api/manual-demo";

export function ManualDemoDetail({ commandId }: { commandId: string }) {
  const load = useCallback(() => manualDemo.detail(commandId), [commandId]);
  const { data, loading, error, reload } = useAsyncData(load, [commandId]);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [conversation, setConversation] = useState<string | null>(null);
  async function act(operation: () => Promise<unknown>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setFailure(null);
    try {
      await operation();
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "Request failed");
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  const evidence = data?.evidence;
  return (
    <main className="space-y-4">
      <h1>Manual BloFin demo attempt</h1>
      <Link className="underline" href="/settings">
        Return to manual demo controls and history
      </Link>
      {loading && <p>Loading stored attempt…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <Button onClick={() => void reload()}>Retry stored detail</Button>
        </div>
      )}
      {data && evidence && (
        <>
          <p>
            {data.symbol} · {data.side === "BUY" ? "Long" : "Short"} ·{" "}
            {data.venue} · {data.origin}
          </p>
          <p>
            {data.requested_contracts} requested contracts ={" "}
            {data.base_quantity} BTC
          </p>
          <p>
            Attempt recorded: {new Date(data.attempted_at).toLocaleString()} ·
            submission started:{" "}
            {data.submitted_at
              ? new Date(data.submitted_at).toLocaleString()
              : "Not recorded"}
          </p>
          <p>
            Account: {data.account_name} ({data.account_id})
          </p>
          <p>
            Execution:{" "}
            {evidence.execution_status?.replaceAll("_", " ") ?? evidence.status}
          </p>
          {data.blocked_reason && (
            <p>
              Blocked before submission:{" "}
              {data.blocked_reason.replaceAll("_", " ")}
            </p>
          )}
          <p>
            Recorded entry fills: {evidence.filled_quantity} contracts · entry
            price: {evidence.average_fill_price ?? "Unverified"}
          </p>
          <p>
            Remaining entry quantity: {evidence.remaining_quantity} contracts ·
            recorded fees: {evidence.fees ?? "Unverified"} USDT
          </p>
          <p>
            Recorded position lifecycle:{" "}
            {evidence.position_status?.replaceAll("_", " ") ?? "Unknown"} ·
            current account evidence:{" "}
            {evidence.account_status?.replaceAll("_", " ") ?? "Unknown"}.
            Account positions are not automatically attributed to this attempt.
          </p>
          <p>
            Planned stop {data.stop} · target {data.target} USDT · current
            protection: {evidence.protection}
          </p>
          {evidence.protection_history?.map((p) => (
            <p key={p.tpsl_id}>
              Native protection history: {p.tpsl_id} · {p.state}. A canceled
              protection record does not establish a position exit.
            </p>
          ))}
          <p>
            Recorded exit fills: {evidence.exit_quantity ?? "0"} contracts ·
            exit price: {evidence.exit_price ?? "Unverified"} · exit fees:{" "}
            {evidence.exit_fees ?? "Unverified"} USDT
          </p>
          {evidence.exit_fills?.map((fill) => (
            <p key={fill.identity}>
              Exit fill {fill.identity}: {fill.quantity} contracts at{" "}
              {fill.price} · {new Date(fill.occurred_at).toLocaleString()} · fee{" "}
              {fill.fee} USDT
            </p>
          ))}
          <p>
            Venue reported fill PnL:{" "}
            {evidence.venue_reported_fill_pnl ?? "Unverified"} USDT. Net PnL and
            funding require separate evidence.
          </p>
          <p>
            Reconciliation:{" "}
            {evidence.reconciliation_freshness?.replaceAll("_", " ") ??
              "Never observed"}{" "}
            · observed:{" "}
            {evidence.observed_at
              ? new Date(evidence.observed_at).toLocaleString()
              : "Not recorded"}
          </p>
          <p>
            Account recovery: {evidence.recovery_status ?? "Unresolved"}.{" "}
            {evidence.recovery_reason}
          </p>
          <p>
            This attempt’s reservation:{" "}
            {evidence.reservation_status ?? "Unknown"}.
          </p>
          {evidence.account_claim_command_ids?.length ? (
            <p>
              Unresolved manual account claims:{" "}
              {evidence.account_claim_command_ids.map((id) => (
                <Link
                  key={id}
                  className="mr-2 underline"
                  href={`/execution/manual-demo/${encodeURIComponent(id)}`}
                >
                  {id}
                </Link>
              ))}
            </p>
          ) : null}
          {evidence.reconciliation_diagnostics?.map((d, i) => (
            <p role="alert" key={`${d.stage}:${i}`}>
              {d.stage}: {d.reason_code} · {d.endpoint_name}
              {d.field_name ? ` · field ${d.field_name}` : ""}
              {d.http_status ? ` · HTTP ${d.http_status}` : ""}
              {d.venue_error_code ? ` · venue ${d.venue_error_code}` : ""}.
              Refresh this same command; do not resubmit.
            </p>
          ))}
          {evidence.missing_evidence.map((note) => (
            <p key={note}>{note}</p>
          ))}
          {evidence.can_reconcile && (
            <Button
              disabled={busy || loading}
              onClick={() =>
                void act(async () => {
                  await manualDemo.reconcile(commandId);
                  setConfirmed(false);
                  await reload();
                })
              }
            >
              Refresh native evidence for this attempt
            </Button>
          )}
          {evidence.can_resolve && (
            <div className="space-y-2">
              <label>
                <input
                  type="checkbox"
                  checked={confirmed}
                  disabled={busy}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />{" "}
                Resolve only this attempt’s account reservation using fresh
                terminal evidence. Keep global safety and unrelated holds.
              </label>
              <Button
                disabled={busy || !confirmed}
                onClick={() =>
                  void act(async () => {
                    await manualDemo.resolve(commandId);
                    setConfirmed(false);
                    await reload();
                  })
                }
              >
                Resolve verified lifecycle
              </Button>
            </div>
          )}
          <Button
            disabled={busy}
            onClick={() =>
              void act(async () => {
                const result = await api.agent.turn({
                  message: `Explain manual BloFin demo command ${commandId}`,
                  action: {
                    name: "paper_trade.read_recorded",
                    arguments: {
                      command_id: commandId,
                      execution_venue: "BLOFIN_DEMO",
                      trade_origin: "manual_demo_test",
                    },
                  },
                });
                setAnswer(result.reply);
                setConversation(result.conversation_id);
              })
            }
          >
            Ask Agent about this exact attempt
          </Button>
          {answer && (
            <section aria-label="Agent explanation">
              <p className="whitespace-pre-wrap">{answer}</p>
              {conversation && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      const result = await api.agent.turn({
                        message: "Explain that trade",
                        conversation_id: conversation,
                      });
                      setAnswer(result.reply);
                    })
                  }
                >
                  Explain that trade
                </Button>
              )}
            </section>
          )}
          {evidence.journal_trade_id && (
            <Link
              className="underline"
              href={`/journal?trade_id=${encodeURIComponent(evidence.journal_trade_id)}`}
            >
              Open this attempt’s Journal projection
            </Link>
          )}
          <details>
            <summary>Stored identities and history</summary>
            <p>Command: {commandId}</p>
            <p>Native order: {evidence.venue_order_id ?? "Unverified"}</p>
            <p>
              Client order: {evidence.client_order_id || "No submission effect"}
            </p>
            <p>
              Protection:{" "}
              {evidence.protection_order_ids?.join(", ") || "Unverified"}
            </p>
            <p>
              Immutable plan: {evidence.revision_id} · hash {data.content_hash}
            </p>
            <p>Journal: {evidence.journal_trade_id ?? "No fill projection"}</p>
          </details>
        </>
      )}
      {failure && <p role="alert">{failure}</p>}
    </main>
  );
}
