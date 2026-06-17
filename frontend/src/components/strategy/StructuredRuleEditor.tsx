"use client";

import { useCallback, useEffect, useState } from "react";
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

const TIMEFRAMES = ["15m", "1h", "4h", "1d"] as const;

const emptyDraft = (): StructuredRules => ({
  primary_timeframe: "4h",
  entry_rules: [{ trigger_type: "ema_pullback", direction: "long", conditions: [], notes: "" }],
  exit_rules: [
    { rule_type: "fixed_stop", value: "2", conditions: [], notes: "" },
    { rule_type: "tp_multiple", r_multiple: "1", conditions: [], notes: "" },
  ],
  no_trade_rules: [],
});

type Props = {
  rules: StructuredRules | null;
  testability: StrategyTestability | null;
  onSave?: (rules: StructuredRules) => void;
  busy?: boolean;
};

export function StructuredRuleEditor({ rules, testability, onSave, busy }: Props) {
  const [draft, setDraft] = useState<StructuredRules>(rules ?? emptyDraft());

  useEffect(() => {
    if (rules) setDraft(rules);
  }, [rules]);

  const updateEntry = useCallback((index: number, patch: Partial<StructuredRules["entry_rules"][0]>) => {
    setDraft((prev) => {
      const next = [...prev.entry_rules];
      next[index] = { ...next[index], ...patch };
      return { ...prev, entry_rules: next };
    });
  }, []);

  const addEntry = () => {
    setDraft((prev) => ({
      ...prev,
      entry_rules: [...prev.entry_rules, { trigger_type: "ema_pullback", direction: "long" }],
    }));
  };

  const removeEntry = (index: number) => {
    setDraft((prev) => ({
      ...prev,
      entry_rules: prev.entry_rules.filter((_, i) => i !== index),
    }));
  };

  const updateExit = (index: number, patch: Partial<StructuredRules["exit_rules"][0]>) => {
    setDraft((prev) => {
      const next = [...prev.exit_rules];
      next[index] = { ...next[index], ...patch };
      return { ...prev, exit_rules: next };
    });
  };

  const addExit = () => {
    setDraft((prev) => ({
      ...prev,
      exit_rules: [...prev.exit_rules, { rule_type: "fixed_stop", value: "2" }],
    }));
  };

  const removeExit = (index: number) => {
    setDraft((prev) => ({
      ...prev,
      exit_rules: prev.exit_rules.filter((_, i) => i !== index),
    }));
  };

  const updateNoTrade = (index: number, patch: Partial<StructuredRules["no_trade_rules"][0]>) => {
    setDraft((prev) => {
      const next = [...prev.no_trade_rules];
      next[index] = { ...next[index], ...patch };
      return { ...prev, no_trade_rules: next };
    });
  };

  const addNoTrade = () => {
    setDraft((prev) => ({
      ...prev,
      no_trade_rules: [...prev.no_trade_rules, { rule_type: "daily_loss_lock" }],
    }));
  };

  const removeNoTrade = (index: number) => {
    setDraft((prev) => ({
      ...prev,
      no_trade_rules: prev.no_trade_rules.filter((_, i) => i !== index),
    }));
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
        <label className="flex flex-col gap-1">
          <span className="text-zinc-400">Primary timeframe</span>
          <select
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
            value={draft.primary_timeframe ?? "4h"}
            onChange={(e) => setDraft((p) => ({ ...p, primary_timeframe: e.target.value }))}
            data-testid="primary-timeframe"
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </label>
        {testability ? (
          <div className="flex flex-wrap items-center gap-2">
            <span data-testid="testability-score">Testability: {testability.score}/100</span>
            <span className="rounded bg-zinc-800 px-2 py-0.5">{testability.band}</span>
            {testability.ready_for_backtest ? (
              <span className="text-emerald-400" data-testid="ready-badge">
                Ready for backtest
              </span>
            ) : testability.not_backtestable_reason ? (
              <span className="text-amber-300/90" data-testid="not-backtestable-reason">
                {testability.not_backtestable_reason}
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
        {testability?.suggested_edits?.length ? (
          <ul className="list-disc pl-4 text-zinc-400" data-testid="suggested-edits">
            {testability.suggested_edits.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        ) : null}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-medium text-zinc-200">Entry triggers</p>
            <button
              type="button"
              className="text-xs text-emerald-400"
              data-testid="add-entry-block"
              onClick={addEntry}
            >
              + Add
            </button>
          </div>
          {draft.entry_rules.map((r, i) => (
            <div
              key={`entry-${i}`}
              className="grid gap-2 rounded border border-zinc-800 p-2 md:grid-cols-4"
              data-testid={`entry-block-${i}`}
            >
              <select
                value={r.trigger_type}
                onChange={(e) => updateEntry(i, { trigger_type: e.target.value })}
                data-testid={`entry-type-${i}`}
              >
                {ENTRY_TRIGGERS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <select
                value={r.direction ?? "long"}
                onChange={(e) => updateEntry(i, { direction: e.target.value })}
              >
                <option value="long">long</option>
                <option value="short">short</option>
              </select>
              <input
                className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 md:col-span-2"
                placeholder="Notes"
                value={r.notes ?? ""}
                onChange={(e) => updateEntry(i, { notes: e.target.value })}
              />
              <button
                type="button"
                className="text-xs text-red-300 md:col-span-4 md:text-right"
                data-testid={`remove-entry-${i}`}
                onClick={() => removeEntry(i)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-medium text-zinc-200">Exit rules</p>
            <button
              type="button"
              className="text-xs text-emerald-400"
              data-testid="add-exit-block"
              onClick={addExit}
            >
              + Add
            </button>
          </div>
          {draft.exit_rules.map((r, i) => (
            <div
              key={`exit-${i}`}
              className="grid gap-2 rounded border border-zinc-800 p-2 md:grid-cols-4"
              data-testid={`exit-block-${i}`}
            >
              <select
                value={r.rule_type}
                onChange={(e) => updateExit(i, { rule_type: e.target.value })}
                data-testid={`exit-type-${i}`}
              >
                {EXIT_RULES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                placeholder="Value / R"
                value={String(r.value ?? r.r_multiple ?? "")}
                onChange={(e) =>
                  updateExit(i, {
                    value: e.target.value,
                    r_multiple: r.rule_type === "tp_multiple" ? e.target.value : r.r_multiple,
                  })
                }
              />
              <input
                className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 md:col-span-2"
                placeholder="Notes"
                value={r.notes ?? ""}
                onChange={(e) => updateExit(i, { notes: e.target.value })}
              />
              <button
                type="button"
                className="text-xs text-red-300 md:col-span-4 md:text-right"
                data-testid={`remove-exit-${i}`}
                onClick={() => removeExit(i)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-medium text-zinc-200">No-trade filters</p>
            <button
              type="button"
              className="text-xs text-emerald-400"
              data-testid="add-notrade-block"
              onClick={addNoTrade}
            >
              + Add
            </button>
          </div>
          {draft.no_trade_rules.length === 0 ? (
            <p className="text-zinc-500">None yet — add filters to improve testability.</p>
          ) : null}
          {draft.no_trade_rules.map((r, i) => (
            <div
              key={`nt-${i}`}
              className="grid gap-2 rounded border border-zinc-800 p-2 md:grid-cols-3"
              data-testid={`notrade-block-${i}`}
            >
              <select
                value={r.rule_type}
                onChange={(e) => updateNoTrade(i, { rule_type: e.target.value })}
              >
                {NO_TRADE_RULES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                placeholder="Notes"
                value={r.notes ?? ""}
                onChange={(e) => updateNoTrade(i, { notes: e.target.value })}
              />
              <button
                type="button"
                className="text-xs text-red-300 text-right"
                data-testid={`remove-notrade-${i}`}
                onClick={() => removeNoTrade(i)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        {onSave ? (
          <button
            type="button"
            disabled={busy}
            className="rounded-lg border border-zinc-700 px-3 py-2 hover:bg-zinc-900 disabled:opacity-50"
            onClick={() => onSave(draft)}
            data-testid="save-structured-rules"
          >
            {busy ? "Saving…" : "Save structured rules"}
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}
