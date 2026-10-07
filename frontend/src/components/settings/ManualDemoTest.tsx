"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { manualDemo, type ManualDemoPreview, type ManualDemoStatus } from "@/lib/api/manual-demo";

export function ManualDemoTest() {
  const [open, setOpen] = useState(false);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState("");
  const [stop, setStop] = useState("");
  const [target, setTarget] = useState("");
  const [preview, setPreview] = useState<ManualDemoPreview | null>(null);
  const [result, setResult] = useState<ManualDemoStatus | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const [sent, setSent] = useState(false);

  async function act(operation: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    try { await operation(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Demo evidence is unavailable. Do not repeat an uncertain confirmation."); }
    finally { pending.current = false; setBusy(false); }
  }
  function changed(update: () => void) {
    update();
    setPreview(null);
    setConfirmed(false);
  }

  return <Card>
    <CardHeader><p className="text-sm">Supervised manual BloFin demo test</p></CardHeader>
    <CardContent className="space-y-3">
      <p className="text-sm text-text-muted">Owner only · BTC market entry · demo funds. Preview and exact confirmation are required. This does not approve a strategy. The server capability must be separately armed after review.</p>
      {!open ? <Button onClick={() => setOpen(true)}>Prepare manual demo test</Button> : <>
        {!sent && <div className="space-y-2">
          <label className="block">Side <select aria-label="Demo side" value={side} onChange={(e) => changed(() => setSide(e.target.value as "BUY" | "SELL"))}><option value="BUY">Long</option><option value="SELL">Short</option></select></label>
          <label className="block">Quantity in contracts <input aria-label="Quantity in contracts" inputMode="decimal" value={quantity} onChange={(e) => changed(() => setQuantity(e.target.value))} /></label>
          <label className="block">Stop (USDT) <input aria-label="Stop (USDT)" inputMode="decimal" value={stop} onChange={(e) => changed(() => setStop(e.target.value))} /></label>
          <label className="block">Target (USDT) <input aria-label="Target (USDT)" inputMode="decimal" value={target} onChange={(e) => changed(() => setTarget(e.target.value))} /></label>
          <Button disabled={busy || !quantity || !stop || !target} onClick={() => void act(async () => { setPreview(null); setConfirmed(false); setPreview(await manualDemo.preview({ symbol: "BTCUSDT", side, order_type: "MARKET", quantity, stop, target })); })}>Preview demo entry</Button>
        </div>}
        {preview && <div className="space-y-2" aria-label="Manual demo entry preview">
          <p>{preview.instrument} · {preview.side === "BUY" ? "Long" : "Short"} · Market</p>
          <p>{preview.quantity} contracts ({preview.base_quantity} BTC) · reference {preview.reference_price} USDT</p>
          <p>Permitted entry range: {preview.entry_lower}–{preview.entry_upper} USDT</p>
          <p>Stop {preview.stop} · target {preview.target} USDT</p>
          <p>Maximum planned loss: {preview.maximum_planned_loss} USDT · gross reward/risk: {Number(preview.gross_reward_risk).toFixed(2)}R</p>
          <p>Preview expires: {new Date(preview.valid_until).toLocaleTimeString()}</p>
          {preview.warnings.map((warning) => <p className="text-sm text-text-muted" key={warning}>{warning}</p>)}
          {!sent && <>
            <label className="block"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I confirm this exact manual demo test plan.</label>
            <Button disabled={busy || !confirmed} onClick={() => void act(async () => {
              setSent(true);
              setResult(await manualDemo.confirm(preview));
            })}>Confirm and submit demo market order</Button>
          </>}
          {sent && !result && <Button disabled={busy} onClick={() => void act(async () => { setResult(await manualDemo.confirm(preview)); })}>Recover this exact confirmation (no resend)</Button>}
        </div>}
        {result && <div role="status" className="space-y-2">
          <p>Manual demo test: {result.status.replaceAll("_", " ")}</p>
          <p>Actual filled contracts: {result.filled_quantity} · remaining: {result.remaining_quantity}</p>
          <p>Actual fill price: {result.average_fill_price ?? "Not verified"} · fees: {result.fees ?? "Not verified"} USDT</p>
          <p>Stop/target protection: {result.protection}</p>
          {result.missing_evidence.map((warning) => <p key={warning}>{warning}</p>)}
          <Button disabled={busy} onClick={() => void act(async () => { setResult(await manualDemo.reconcile(result.command_id)); })}>Refresh venue evidence</Button>
          {Number(result.remaining_quantity) > 0 && <Button disabled={busy} onClick={() => void act(async () => { setResult(await manualDemo.cancel(result.command_id)); })}>Cancel unfilled entry remainder</Button>}
          <details><summary>Stored evidence</summary><p>Command: {result.command_id}</p><p>Client order: {result.client_order_id}</p><p>Venue order: {result.venue_order_id ?? "Not verified"}</p><p>Protection orders: {result.protection_order_ids?.join(", ") || "Not verified"}</p><p>Plan: {result.revision_id}</p><p>Hash: {preview?.content_hash}</p><p>Journal: {result.journal_trade_id ?? "No actual fill recorded"}</p></details>
        </div>}
      </>}
      {error && <p role="alert">{error}</p>}
    </CardContent>
  </Card>;
}
