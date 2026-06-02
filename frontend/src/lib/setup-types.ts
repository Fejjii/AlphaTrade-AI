import type { StrategyId } from "@/lib/api/types";

export const SETUP_TYPE_OPTIONS: { value: StrategyId; label: string }[] = [
  { value: "htf_trend_pullback", label: "HTF trend pullback" },
  { value: "liquidity_sweep_reversal", label: "Liquidity sweep reversal" },
  { value: "countertrend_short_build", label: "Countertrend short build" },
  { value: "passive_level_order", label: "Passive level order" },
  { value: "profit_protection", label: "Profit protection" },
  { value: "green_day_guard", label: "Green day guard" },
  { value: "mental_capital_guard", label: "Mental capital guard" },
  { value: "manual_review", label: "Manual review" },
];

export const MISTAKE_TAG_SUGGESTIONS = [
  "fomo",
  "no_stop",
  "oversize",
  "revenge_trade",
  "ignored_plan",
  "chased_entry",
];

export const EMOTION_TAG_SUGGESTIONS = [
  "calm",
  "anxious",
  "fearful",
  "overconfident",
  "frustrated",
  "impatient",
];
