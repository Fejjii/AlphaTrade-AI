import type { DataNumberTone } from "@/components/ui/data-number";

export {
  addDays,
  containsCurrencySymbol,
  formatDateRangeLabel,
  formatMonetary,
  formatPercent,
  formatProfitFactor,
  formatSignedPercent,
  formatTrendLabel,
  isoDateOnly,
  parseDecimal,
} from "@/lib/format";

export function monetaryTone(value: number | null | undefined): DataNumberTone {
  if (value === null || value === undefined || value === 0) return "muted";
  return value > 0 ? "positive" : "negative";
}
