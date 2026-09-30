"use client";

import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { WatcherSymbolRuntimeStatus, WatcherWatchlistSlot } from "@/lib/api/types";

export const DEFAULT_WATCHLIST_SLOTS: WatcherWatchlistSlot[] = [
  { position: 1, symbol: "BTCUSDT", enabled: true },
  { position: 2, symbol: "ZECUSDT", enabled: true },
  { position: 3, symbol: "ETHUSDT", enabled: true },
  { position: 4, symbol: "TAOUSDT", enabled: true },
  { position: 5, symbol: "HYPEUSDT", enabled: true },
];

function moveSlot(slots: WatcherWatchlistSlot[], index: number, direction: -1 | 1) {
  const next = index + direction;
  if (next < 0 || next >= slots.length) return slots;
  const copy = slots.slice();
  const current = copy[index];
  const neighbor = copy[next];
  if (!current || !neighbor) return slots;
  copy[index] = { ...neighbor, position: current.position };
  copy[next] = { ...current, position: neighbor.position };
  return copy.map((slot, slotIndex) => ({ ...slot, position: slotIndex + 1 }));
}

export function WatcherWatchlistEditor({
  slots,
  statuses,
  saving = false,
  message = null,
  onChange,
  onSave,
}: {
  slots: WatcherWatchlistSlot[];
  statuses: WatcherSymbolRuntimeStatus[];
  saving?: boolean;
  message?: string | null;
  onChange: (slots: WatcherWatchlistSlot[]) => void;
  onSave: () => void;
}) {
  const statusByPosition = new Map(statuses.map((row) => [row.position, row]));
  return (
    <Card data-testid="watcher-watchlist">
      <CardHeader>
        <CardTitle className="text-base">Watcher watchlist</CardTitle>
        <p className="text-xs text-text-muted">
          Five paper slots. One Watcher scans them in order. Unsupported markets stay unavailable.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {slots.map((slot, index) => {
          const status = statusByPosition.get(slot.position);
          return (
            <div
              key={slot.position}
              className="grid gap-2 border-b border-border pb-3 md:grid-cols-[auto_1fr_auto]"
              data-testid={`watchlist-slot-${slot.position}`}
            >
              <div className="flex items-center gap-2">
                <span className="w-12 text-xs text-text-muted">Slot {slot.position}</span>
                <Input
                  aria-label={`Symbol for slot ${slot.position}`}
                  value={slot.symbol}
                  className="w-36"
                  onChange={(event) => {
                    const next = slots.slice();
                    const current = next[index];
                    if (!current) return;
                    next[index] = { ...current, symbol: event.target.value.toUpperCase() };
                    onChange(next);
                  }}
                />
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={slot.enabled}
                    aria-label={`Enable slot ${slot.position}`}
                    onChange={(event) => {
                      const next = slots.slice();
                      const current = next[index];
                      if (!current) return;
                      next[index] = { ...current, enabled: event.target.checked };
                      onChange(next);
                    }}
                  />
                  Enabled
                </label>
              </div>
              <p className="text-xs text-zinc-300" data-testid={`watchlist-status-${slot.position}`}>
                {status ? (
                  <>
                    <StatusBadge
                      label={status.error_state ? "Unavailable" : status.market_source}
                      tone={status.error_state ? "warn" : "healthy"}
                    />{" "}
                    {status.freshness} · {status.setup_state}
                    {status.alert_state !== "none" ? ` · ${status.alert_state}` : ""}
                    {status.error_state ? ` · ${status.error_state}` : ""}
                  </>
                ) : (
                  "Status not loaded"
                )}
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  aria-label={`Move slot ${slot.position} up`}
                  disabled={index === 0}
                  onClick={() => onChange(moveSlot(slots, index, -1))}
                >
                  Up
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  aria-label={`Move slot ${slot.position} down`}
                  disabled={index === slots.length - 1}
                  onClick={() => onChange(moveSlot(slots, index, 1))}
                >
                  Down
                </Button>
              </div>
            </div>
          );
        })}
        <div className="flex items-center gap-3">
          <Button type="button" onClick={onSave} disabled={saving} data-testid="watchlist-save">
            {saving ? "Saving" : "Save watchlist"}
          </Button>
          {message ? <p className="text-xs text-text-muted">{message}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function WatcherWatchlistSection() {
  const [slots, setSlots] = useState<WatcherWatchlistSlot[]>(DEFAULT_WATCHLIST_SLOTS);
  const [statuses, setStatuses] = useState<WatcherSymbolRuntimeStatus[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api.watcherWatchlist
      .configuration()
      .then((config) => {
        if (!cancelled && config.slots.length === 5) setSlots(config.slots);
      })
      .catch(() => {
        if (!cancelled) setMessage("Watchlist configuration is not loaded yet.");
      });
    void api.watcherWatchlist
      .status()
      .then((status) => {
        if (!cancelled) setStatuses(status.symbols);
      })
      .catch(() => {
        if (!cancelled) setStatuses([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <WatcherWatchlistEditor
      slots={slots}
      statuses={statuses}
      saving={saving}
      message={message}
      onChange={setSlots}
      onSave={() => {
        setSaving(true);
        setMessage(null);
        void api.watcherWatchlist
          .replace(slots.map((slot) => ({ symbol: slot.symbol, enabled: slot.enabled })))
          .then((config) => {
            setSlots(config.slots);
            setMessage("Watchlist saved. Paper only.");
          })
          .catch(() => {
            setMessage("Watchlist was not saved.");
          })
          .finally(() => setSaving(false));
      }}
    />
  );
}
