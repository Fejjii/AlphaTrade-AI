"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { SETUP_TYPE_OPTIONS } from "@/lib/setup-types";
import type { StrategyCard } from "@/lib/api/types";

const VALIDATION_STATUSES = [
  "draft",
  "in_review",
  "validated",
  "restricted",
  "retired",
  "needs_revision",
  "deprecated",
] as const;

const TIMEFRAME_OPTIONS = ["15m", "1h", "4h", "1d"] as const;

function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function listToLines(items: string[]): string {
  return items.join("\n");
}

export function emptyStrategyCard(name = "New strategy"): StrategyCard {
  return {
    strategy_name: name,
    market_type: "crypto_perp",
    asset_universe: ["BTCUSDT"],
    timeframes: ["4h"],
    entry_conditions: ["Define entry trigger"],
    confirmation_conditions: ["Define confirmation"],
    invalidation: ["Define invalidation"],
    stop_loss: ["Below invalidation"],
    take_profit_plan: ["TP1 at resistance"],
    runner_plan: ["Trail after TP1"],
    position_sizing: ["Max 1% risk"],
    add_rules: ["No adds until TP1"],
    no_trade_rules: ["Skip low liquidity"],
    backtest_rules: ["Placeholder — not run"],
    success_criteria: ["Paper win rate > 45%"],
    validation_status: "draft",
  };
}

export function StrategyCardForm({
  initial,
  setupType,
  onSetupTypeChange,
  onSubmit,
  submitLabel = "Save strategy",
  busy = false,
}: {
  initial: StrategyCard;
  setupType: string;
  onSetupTypeChange?: (value: string) => void;
  onSubmit: (card: StrategyCard) => void | Promise<void>;
  submitLabel?: string;
  busy?: boolean;
}) {
  const [card, setCard] = useState(initial);

  function updateListField(field: keyof StrategyCard, value: string) {
    setCard((prev) => ({ ...prev, [field]: linesToList(value) }));
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void onSubmit(card);
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="strategy_name">Strategy name</Label>
          <Input
            id="strategy_name"
            value={card.strategy_name}
            onChange={(e) => setCard((p) => ({ ...p, strategy_name: e.target.value }))}
          />
        </div>
        {onSetupTypeChange ? (
          <div className="space-y-2">
            <Label htmlFor="setup_type">Setup type</Label>
            <select
              id="setup_type"
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
              value={setupType}
              onChange={(e) => onSetupTypeChange(e.target.value)}
            >
              {SETUP_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        ) : null}
        <div className="space-y-2">
          <Label htmlFor="validation_status">Validation status</Label>
          <select
            id="validation_status"
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
            value={card.validation_status}
            onChange={(e) =>
              setCard((p) => ({ ...p, validation_status: e.target.value }))
            }
          >
            {VALIDATION_STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace("_", " ")}</option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="asset_universe">Asset universe (comma separated)</Label>
          <Input
            id="asset_universe"
            value={card.asset_universe.join(", ")}
            onChange={(e) =>
              setCard((p) => ({
                ...p,
                asset_universe: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              }))
            }
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="timeframes">Timeframes</Label>
          <select
            id="timeframes"
            multiple
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
            value={card.timeframes}
            onChange={(e) => {
              const selected = Array.from(e.target.selectedOptions).map((o) => o.value);
              setCard((p) => ({ ...p, timeframes: selected as StrategyCard["timeframes"] }));
            }}
          >
            {TIMEFRAME_OPTIONS.map((tf) => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
        </div>
      </div>

      {(
        [
          ["entry_conditions", "Entry conditions"],
          ["confirmation_conditions", "Confirmation"],
          ["invalidation", "Invalidation"],
          ["stop_loss", "Stop loss"],
          ["take_profit_plan", "Take profit"],
          ["runner_plan", "Runner plan"],
          ["no_trade_rules", "No-trade rules"],
        ] as const
      ).map(([field, label]) => (
        <div key={field} className="space-y-2">
          <Label>{label} (one per line)</Label>
          <textarea
            className="min-h-[72px] w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
            value={listToLines(card[field])}
            onChange={(e) => updateListField(field, e.target.value)}
          />
        </div>
      ))}

      <Button type="submit" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
    </form>
  );
}
