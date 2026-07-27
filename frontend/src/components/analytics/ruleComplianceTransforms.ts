import type { JournalStatsBucket, JournalStatsResponse, TradeRuleCompliance } from "@/lib/api/types";

import { parseDecimal } from "./format";

export const RULE_COMPLIANCE_ORDER: TradeRuleCompliance[] = [
  "compliant",
  "partial",
  "violated",
  "unassessed",
];

export type RuleComplianceMetric = "win_rate" | "expectancy";

export type RuleComplianceRow = {
  key: TradeRuleCompliance;
  label: string;
  tradeCount: number;
  winRate: number | null;
  expectancy: number | null;
  confidence: string;
  assessed: boolean;
};

const LABELS: Record<TradeRuleCompliance, string> = {
  compliant: "Compliant",
  partial: "Partial",
  violated: "Violated",
  unassessed: "Unassessed",
};

function emptyRow(key: TradeRuleCompliance): RuleComplianceRow {
  return {
    key,
    label: LABELS[key],
    tradeCount: 0,
    winRate: null,
    expectancy: null,
    confidence: "insufficient",
    assessed: key !== "unassessed",
  };
}

function bucketKey(bucket: JournalStatsBucket): TradeRuleCompliance | null {
  const candidates = [bucket.key, bucket.group_id, bucket.label]
    .filter(Boolean)
    .map((value) => String(value).toLowerCase());
  for (const candidate of candidates) {
    if ((RULE_COMPLIANCE_ORDER as string[]).includes(candidate)) {
      return candidate as TradeRuleCompliance;
    }
  }
  return null;
}

/** Always returns all four compliance buckets, including unassessed. */
export function buildRuleComplianceRows(response: JournalStatsResponse | null): RuleComplianceRow[] {
  const byKey = new Map<TradeRuleCompliance, RuleComplianceRow>();
  for (const key of RULE_COMPLIANCE_ORDER) byKey.set(key, emptyRow(key));

  for (const bucket of response?.buckets ?? []) {
    const key = bucketKey(bucket);
    if (!key) continue;
    byKey.set(key, {
      key,
      label: LABELS[key],
      tradeCount: bucket.metrics.trade_count,
      winRate: bucket.metrics.win_rate,
      expectancy: parseDecimal(bucket.metrics.expectancy),
      confidence: bucket.metrics.confidence,
      assessed: key !== "unassessed",
    });
  }

  return RULE_COMPLIANCE_ORDER.map((key) => byKey.get(key)!);
}

export function totalRuleComplianceSample(rows: RuleComplianceRow[]): number {
  return rows.reduce((sum, row) => sum + row.tradeCount, 0);
}
