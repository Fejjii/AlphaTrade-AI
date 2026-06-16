"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { StrategyTestability, StructuredRules } from "@/lib/api/types";

const ENTRY_TRIGGERS = [
  "ema_pullback",
  "breakout",
  "liquidity_sweep",
  "reclaim",
  "failed_breakout",
  "rsi_threshold",
  "volume_confirmation",
  "trend_alignment",
] as const;

const EXIT_RULES = [
  "fixed_stop",
  "atr_stop",
  "swing_stop",
  "tp_multiple",
  "tp_price_levels",
  "partial_tp",
  "runner_structure_break",
] as const;

const NO_TRADE_RULES = [
  "low_volume",
  "high_funding",
  "weekend_chop",
  "daily_loss_lock",
  "green_day_protection",
  "htf_conflict",
] as const;

type Props = {
  rules: StructuredRules | null;
  testability: StrategyTestability | null;
  onSave?: (rules: StructuredRules) => void;
  busy?: boolean;
};

export function StructuredRuleEditor({ rules, testability, onSave, busy }: Props) {
  const draft: StructuredRules = rules ?? {
    primary_timeframe: "4h",
    entry_rules: [{ trigger_type: "ema_pullback", direction: "long" }],
    exit_rules: [
      { rule_type: "fixed_stop", value: "2" },
      { rule_type: "tp_multiple", r_multiple: "1" },
    ],
    no_trade_rules: [],
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Structured rule editor</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        <p className="text-zinc-400">
          Machine-testable rule blocks improve backtest reliability. Real trading remains disabled.
        </p>
        {testability ? (
          <div className="flex flex-wrap items-center gap-2">
            <span data-testid="testability-score">Testability: {testability.score}/100</span>
            <span className="rounded bg-zinc-800 px-2 py-0.5">{testability.band}</span>
            {testability.ready_for_backtest ? (
              <span className="text-emerald-400" data-testid="ready-badge">
                Ready for backtest
              </span>
            ) : null}
          </div>
        ) : null}
        {testability?.missing_fields?.length ? (
          <ul className="list-disc pl-4 text-amber-300/90" data-testid="missing-fields">
            {testability.missing_fields.map((f) => (
              <li key={f.field_key}>{f.label}</li>
            ))}
          </ul>
        ) : null}
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <p className="mb-1 font-medium text-zinc-200">Entry triggers</p>
            <ul className="list-disc pl-4">
              {draft.entry_rules.map((r, i) => (
                <li key={`entry-${i}`}>{r.trigger_type}</li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-zinc-500">{ENTRY_TRIGGERS.join(", ")}</p>
          </div>
          <div>
            <p className="mb-1 font-medium text-zinc-200">Exit rules</p>
            <ul className="list-disc pl-4">
              {draft.exit_rules.map((r, i) => (
                <li key={`exit-${i}`}>{r.rule_type}</li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-zinc-500">{EXIT_RULES.join(", ")}</p>
          </div>
          <div>
            <p className="mb-1 font-medium text-zinc-200">No-trade filters</p>
            <ul className="list-disc pl-4">
              {draft.no_trade_rules.length ? (
                draft.no_trade_rules.map((r, i) => <li key={`nt-${i}`}>{r.rule_type}</li>)
              ) : (
                <li className="text-zinc-500">None yet</li>
              )}
            </ul>
            <p className="mt-1 text-xs text-zinc-500">{NO_TRADE_RULES.join(", ")}</p>
          </div>
        </div>
        {onSave ? (
          <button
            type="button"
            disabled={busy}
            className="rounded-lg border border-zinc-700 px-3 py-2 hover:bg-zinc-900 disabled:opacity-50"
            onClick={() => onSave(draft)}
          >
            {busy ? "Saving…" : "Save structured rules"}
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}
