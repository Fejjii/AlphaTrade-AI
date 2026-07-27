import type { SetupGroupBy } from "./filterValidation";
import { UNASSIGNED_BUCKET_KEY, type SetupBucketRow } from "./setupBucketTransforms";

export type SetupBucketLinkSet = {
  journalHref: string;
  analyticsHref: string;
  /** Shown when group_by=setup — name buckets have no setup-definition UUID. */
  exactFilterNote: string | null;
  /** Param used for identity deep links, if any. */
  identityParam: "setup_id" | "user_strategy_id" | null;
  identityValue: string | null;
};

function withGroupBy(base: string, groupBy: SetupGroupBy): string {
  const params = new URLSearchParams();
  if (base.includes("?")) {
    const [path, query] = base.split("?", 2);
    const existing = new URLSearchParams(query);
    for (const [key, value] of existing.entries()) params.set(key, value);
    if (groupBy !== "setup") params.set("group_by", groupBy);
    const qs = params.toString();
    return qs ? `${path}?${qs}` : path;
  }
  if (groupBy !== "setup") params.set("group_by", groupBy);
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

/**
 * Build Analytics + Journal Statistics links from the verified journal-statistics
 * grouping contract — never infer identity type from UUID shape or display name.
 */
export function buildSetupBucketLinks(
  row: SetupBucketRow,
  groupBy: SetupGroupBy,
): SetupBucketLinkSet {
  if (row.key === UNASSIGNED_BUCKET_KEY || row.unassigned) {
    return {
      journalHref: "/journal/statistics",
      analyticsHref: withGroupBy("/analytics?tab=setups", groupBy),
      exactFilterNote: null,
      identityParam: null,
      identityValue: null,
    };
  }

  switch (groupBy) {
    case "setup":
      // key is shared setup name; group_id is null — no exact setup UUID drill-down.
      return {
        journalHref: "/journal/statistics",
        analyticsHref: withGroupBy("/analytics?tab=setups", groupBy),
        exactFilterNote:
          "Exact setup filtering requires Setup version grouping (setup-definition UUID).",
        identityParam: null,
        identityValue: null,
      };
    case "setup_version": {
      const setupId = row.groupId;
      if (!setupId) {
        return {
          journalHref: "/journal/statistics",
          analyticsHref: withGroupBy("/analytics?tab=setups", groupBy),
          exactFilterNote: null,
          identityParam: null,
          identityValue: null,
        };
      }
      return {
        journalHref: `/journal/statistics?setup_id=${encodeURIComponent(setupId)}`,
        analyticsHref: `/analytics?tab=setups&group_by=setup_version&setup_id=${encodeURIComponent(setupId)}`,
        exactFilterNote: null,
        identityParam: "setup_id",
        identityValue: setupId,
      };
    }
    case "strategy": {
      const strategyId = row.groupId;
      if (!strategyId) {
        return {
          journalHref: "/journal/statistics",
          analyticsHref: withGroupBy("/analytics?tab=setups", groupBy),
          exactFilterNote: null,
          identityParam: null,
          identityValue: null,
        };
      }
      return {
        journalHref: `/journal/statistics?user_strategy_id=${encodeURIComponent(strategyId)}`,
        analyticsHref: `/analytics?tab=setups&group_by=strategy&user_strategy_id=${encodeURIComponent(strategyId)}`,
        exactFilterNote: null,
        identityParam: "user_strategy_id",
        identityValue: strategyId,
      };
    }
    default:
      return {
        journalHref: "/journal/statistics",
        analyticsHref: "/analytics?tab=setups",
        exactFilterNote: null,
        identityParam: null,
        identityValue: null,
      };
  }
}
