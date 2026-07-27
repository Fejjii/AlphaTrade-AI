import type { JournalStatsBucket, SampleConfidence } from "@/lib/api/types";

import { parseDecimal } from "./format";

export const SETUP_CHART_MOBILE_CAP = 8;
export const UNASSIGNED_BUCKET_KEY = "unassigned";

export type SetupBucketRow = {
  key: string;
  groupId: string | null;
  label: string;
  displayLabel: string;
  tradeCount: number;
  wins: number;
  losses: number;
  breakeven: number;
  winRate: number | null;
  winRatePct: number | null;
  expectancy: number | null;
  expectancyRaw: string | null;
  averageR: number | null;
  rSampleCount: number;
  confidence: SampleConfidence;
  insufficient: boolean;
  unassigned: boolean;
  noPnlData: boolean;
};

const CONFIDENCE_RANK: Record<SampleConfidence, number> = {
  high: 0,
  moderate: 1,
  low: 2,
  insufficient: 3,
};

function collideAwareLabel(bucket: JournalStatsBucket, labelCounts: Map<string, number>): string {
  const count = labelCounts.get(bucket.label) ?? 0;
  if (count <= 1) return bucket.label;
  // Preserve colliding display names as distinct identities — append stable key suffix.
  const shortKey = bucket.key.length > 8 ? `${bucket.key.slice(0, 8)}…` : bucket.key;
  return `${bucket.label} (${shortKey})`;
}

export function buildSetupBucketRows(buckets: JournalStatsBucket[]): SetupBucketRow[] {
  const labelCounts = new Map<string, number>();
  for (const bucket of buckets) {
    labelCounts.set(bucket.label, (labelCounts.get(bucket.label) ?? 0) + 1);
  }

  const rows: SetupBucketRow[] = buckets.map((bucket) => {
    const expectancyRaw = bucket.metrics.expectancy;
    const expectancy = parseDecimal(expectancyRaw);
    const noPnlData = expectancyRaw === null || expectancyRaw === undefined;
    const insufficient = bucket.metrics.confidence === "insufficient";
    const unassigned = bucket.key === UNASSIGNED_BUCKET_KEY;
    return {
      key: bucket.key,
      groupId: bucket.group_id ?? null,
      label: bucket.label,
      displayLabel: collideAwareLabel(bucket, labelCounts),
      tradeCount: bucket.metrics.trade_count,
      wins: bucket.metrics.wins,
      losses: bucket.metrics.losses,
      breakeven: bucket.metrics.breakeven,
      winRate: bucket.metrics.win_rate,
      winRatePct:
        bucket.metrics.win_rate === null || bucket.metrics.win_rate === undefined
          ? null
          : bucket.metrics.win_rate * 100,
      expectancy,
      expectancyRaw: expectancyRaw ?? null,
      averageR: bucket.metrics.average_r,
      rSampleCount: bucket.metrics.r_sample_count,
      confidence: bucket.metrics.confidence,
      insufficient,
      unassigned,
      noPnlData,
    };
  });

  rows.sort((a, b) => {
    if (a.unassigned !== b.unassigned) return a.unassigned ? 1 : -1;
    if (a.insufficient !== b.insufficient) return a.insufficient ? 1 : -1;
    const conf = CONFIDENCE_RANK[a.confidence] - CONFIDENCE_RANK[b.confidence];
    if (conf !== 0) return conf;
    if (b.tradeCount !== a.tradeCount) return b.tradeCount - a.tradeCount;
    const labelCmp = a.label.localeCompare(b.label);
    if (labelCmp !== 0) return labelCmp;
    return a.key.localeCompare(b.key);
  });

  return rows;
}

export function visibleSetupChartRows(
  rows: SetupBucketRow[],
  showAll: boolean,
  cap = SETUP_CHART_MOBILE_CAP,
): { visible: SetupBucketRow[]; hiddenCount: number } {
  if (showAll || rows.length <= cap) {
    return { visible: rows, hiddenCount: 0 };
  }
  return { visible: rows.slice(0, cap), hiddenCount: rows.length - cap };
}
