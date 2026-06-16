"use client";

import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api } from "@/lib/api";
import type { ManualLevelType } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

const LEVEL_TYPES: ManualLevelType[] = [
  "support",
  "resistance",
  "fibonacci",
  "trend_line",
  "vwap",
  "liquidity_zone",
  "previous_high",
  "previous_low",
  "user_note",
];

export default function ManualLevelsPage() {
  const [symbolFilter, setSymbolFilter] = useState("");
  const loader = useCallback(
    () => api.manualLevels.list(symbolFilter ? { symbol: symbolFilter } : undefined),
    [symbolFilter],
  );
  const { data, loading, error, reload } = useAsyncData(loader, [symbolFilter]);

  const [symbol, setSymbol] = useState("BTCUSDT");
  const [levelType, setLevelType] = useState<ManualLevelType>("support");
  const [price, setPrice] = useState("");
  const [priceLow, setPriceLow] = useState("");
  const [priceHigh, setPriceHigh] = useState("");
  const [timeframe, setTimeframe] = useState("4h");
  const [notes, setNotes] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function resetForm() {
    setEditingId(null);
    setPrice("");
    setPriceLow("");
    setPriceHigh("");
    setNotes("");
    setEnabled(true);
  }

  async function saveLevel() {
    setBusy(true);
    setFormError(null);
    const body = {
      symbol,
      exchange: "mock",
      level_type: levelType,
      timeframe,
      price: price || undefined,
      price_low: priceLow || undefined,
      price_high: priceHigh || undefined,
      notes: notes || undefined,
      enabled,
    };
    try {
      if (editingId) {
        await api.manualLevels.update(editingId, body);
      } else {
        await api.manualLevels.create(body);
      }
      resetForm();
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function deleteLevel(id: string) {
    await api.manualLevels.delete(id);
    await reload();
  }

  function startEdit(level: {
    id: string;
    symbol: string;
    level_type: ManualLevelType;
    price?: string | null;
    price_low?: string | null;
    price_high?: string | null;
    timeframe?: string | null;
    notes?: string | null;
    enabled: boolean;
  }) {
    setEditingId(level.id);
    setSymbol(level.symbol);
    setLevelType(level.level_type);
    setPrice(level.price ?? "");
    setPriceLow(level.price_low ?? "");
    setPriceHigh(level.price_high ?? "");
    setTimeframe(level.timeframe ?? "4h");
    setNotes(level.notes ?? "");
    setEnabled(level.enabled);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Manual Levels</h1>
        <p className="text-sm text-zinc-400">
          Chart levels feed pre-trade analysis (paper only).{" "}
          <a href="/pre-trade" className="text-zinc-200 underline">Run pre-trade analysis</a>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{editingId ? "Edit level" : "Add level"}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Symbol</Label>
            <Input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
          </div>
          <div className="space-y-2">
            <Label>Level type</Label>
            <select
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
              value={levelType}
              onChange={(e) => setLevelType(e.target.value as ManualLevelType)}
            >
              {LEVEL_TYPES.map((t) => (
                <option key={t} value={t}>{t.replace("_", " ")}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label>Price</Label>
            <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Single price" />
          </div>
          <div className="space-y-2">
            <Label>Zone low / high</Label>
            <div className="flex gap-2">
              <Input value={priceLow} onChange={(e) => setPriceLow(e.target.value)} placeholder="Low" />
              <Input value={priceHigh} onChange={(e) => setPriceHigh(e.target.value)} placeholder="High" />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Timeframe</Label>
            <Input value={timeframe} onChange={(e) => setTimeframe(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Notes</Label>
            <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <Label>Active</Label>
          </div>
          <div className="flex gap-2 sm:col-span-2">
            <Button disabled={busy} onClick={() => void saveLevel()}>
              {busy ? "Saving…" : editingId ? "Update level" : "Add level"}
            </Button>
            {editingId ? (
              <Button variant="outline" onClick={resetForm}>Cancel edit</Button>
            ) : null}
          </div>
          {formError ? <p className="text-sm text-red-400 sm:col-span-2">{formError}</p> : null}
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Input
          placeholder="Filter symbol"
          value={symbolFilter}
          onChange={(e) => setSymbolFilter(e.target.value.toUpperCase())}
        />
      </div>

      {loading ? <LoadingState label="Loading levels…" /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {data?.items.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((level) => (
            <Card key={level.id}>
              <CardHeader>
                <CardTitle className="text-base">
                  {level.symbol} · {level.level_type.replace("_", " ")}
                  {!level.enabled ? " (inactive)" : ""}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-zinc-300">
                {level.price ? <p>Price: {formatDecimal(level.price)}</p> : null}
                {level.price_low || level.price_high ? (
                  <p>Zone: {level.price_low ?? "—"} – {level.price_high ?? "—"}</p>
                ) : null}
                {level.timeframe ? <p>TF: {level.timeframe}</p> : null}
                {level.notes ? <p>{level.notes}</p> : null}
                <div className="flex gap-2 pt-2">
                  <Button size="sm" variant="secondary" onClick={() => startEdit(level)}>Edit</Button>
                  <Button size="sm" variant="outline" onClick={() => void deleteLevel(level.id)}>Delete</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {data && !data.items.length ? (
        <EmptyState title="No manual levels" description="Add levels above or via AI Workspace." />
      ) : null}
    </div>
  );
}
