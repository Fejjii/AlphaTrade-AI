import type { SetupGroupBy } from "./filterValidation";

export type SetupGroupCopy = {
  entitySingular: string;
  entityPlural: string;
  winRateChartTitle: string;
  winRateSourceLabel: string;
  winRateEmptyTitle: string;
  winRateEmptyDescription: string;
  winRateListAriaLabel: string;
  winRateA11yCaption: string;
  expectancySourceLabel: string;
  expectancyEmptyTitle: string;
  expectancyEmptyDescription: string;
  expectancyListAriaLabel: string;
  expectancyA11yCaption: string;
  bucketTableTitle: string;
  bucketTableSourceLabel: string;
  bucketTableEmptyTitle: string;
  bucketTableEmptyDescription: string;
  bucketTableCaption: string;
  groupToggleAriaLabel: string;
};

const COPY: Record<SetupGroupBy, SetupGroupCopy> = {
  setup: {
    entitySingular: "setup",
    entityPlural: "setups",
    winRateChartTitle: "Which setups win most often — with enough sample to matter?",
    winRateSourceLabel: "GET /journal/statistics · group_by setup buckets · win_rate",
    winRateEmptyTitle: "No closed trades have a recorded setup in this range.",
    winRateEmptyDescription:
      "Journal closed trades with a setup definition, or widen filters.",
    winRateListAriaLabel: "Setup win rates",
    winRateA11yCaption: "Setup win-rate values (journal setup identity by key)",
    expectancySourceLabel: "GET /journal/statistics · group_by setup buckets · expectancy",
    expectancyEmptyTitle: "No closed trades have a recorded setup in this range.",
    expectancyEmptyDescription:
      "Journal closed trades with a setup definition, or widen filters.",
    expectancyListAriaLabel: "Setup expectancy",
    expectancyA11yCaption: "Setup expectancy values (journal setup identity by key)",
    bucketTableTitle: "Setup buckets",
    bucketTableSourceLabel: "GET /journal/statistics · setup buckets",
    bucketTableEmptyTitle: "No setup buckets in this range",
    bucketTableEmptyDescription: "Closed journal trades with setup assignments appear here.",
    bucketTableCaption: "Journal setup buckets with identity from group_by contract",
    groupToggleAriaLabel: "Group setups by",
  },
  setup_version: {
    entitySingular: "setup version",
    entityPlural: "setup versions",
    winRateChartTitle: "Which setup versions win most often — with enough sample to matter?",
    winRateSourceLabel: "GET /journal/statistics · group_by setup_version buckets · win_rate",
    winRateEmptyTitle: "No closed trades have a recorded setup version in this range.",
    winRateEmptyDescription:
      "Journal closed trades with a setup-definition UUID, or widen filters.",
    winRateListAriaLabel: "Setup version win rates",
    winRateA11yCaption: "Setup version win-rate values (journal setup identity by key)",
    expectancySourceLabel: "GET /journal/statistics · group_by setup_version buckets · expectancy",
    expectancyEmptyTitle: "No closed trades have a recorded setup version in this range.",
    expectancyEmptyDescription:
      "Journal closed trades with a setup-definition UUID, or widen filters.",
    expectancyListAriaLabel: "Setup version expectancy",
    expectancyA11yCaption: "Setup version expectancy values (journal setup identity by key)",
    bucketTableTitle: "Setup version buckets",
    bucketTableSourceLabel: "GET /journal/statistics · setup_version buckets",
    bucketTableEmptyTitle: "No setup version buckets in this range",
    bucketTableEmptyDescription:
      "Closed journal trades with setup-definition assignments appear here.",
    bucketTableCaption: "Journal setup version buckets with identity from group_by contract",
    groupToggleAriaLabel: "Group setup versions by",
  },
  strategy: {
    entitySingular: "strategy",
    entityPlural: "strategies",
    winRateChartTitle: "Which strategies win most often — with enough sample to matter?",
    winRateSourceLabel: "GET /journal/statistics · group_by strategy buckets · win_rate",
    winRateEmptyTitle: "No closed trades have a recorded strategy in this range.",
    winRateEmptyDescription:
      "Journal closed trades with a strategy assignment, or widen filters.",
    winRateListAriaLabel: "Strategy win rates",
    winRateA11yCaption: "Strategy win-rate values (journal strategy identity by key)",
    expectancySourceLabel: "GET /journal/statistics · group_by strategy buckets · expectancy",
    expectancyEmptyTitle: "No closed trades have a recorded strategy in this range.",
    expectancyEmptyDescription:
      "Journal closed trades with a strategy assignment, or widen filters.",
    expectancyListAriaLabel: "Strategy expectancy",
    expectancyA11yCaption: "Strategy expectancy values (journal strategy identity by key)",
    bucketTableTitle: "Strategy buckets",
    bucketTableSourceLabel: "GET /journal/statistics · strategy buckets",
    bucketTableEmptyTitle: "No strategy buckets in this range",
    bucketTableEmptyDescription: "Closed journal trades with strategy assignments appear here.",
    bucketTableCaption: "Journal strategy buckets with identity from group_by contract",
    groupToggleAriaLabel: "Group strategies by",
  },
};

export function setupGroupCopy(groupBy: SetupGroupBy): SetupGroupCopy {
  return COPY[groupBy];
}

export function setupWinRateAriaLabel(
  groupBy: SetupGroupBy,
  bucketCount: number,
  highestLabel: string | null,
  highestRate: string | null,
): string {
  const { entitySingular, entityPlural } = setupGroupCopy(groupBy);
  if (bucketCount === 0) {
    return `${entitySingular.charAt(0).toUpperCase()}${entitySingular.slice(1)} win-rate chart with no data`;
  }
  const base = `${entitySingular.charAt(0).toUpperCase()}${entitySingular.slice(1)} win-rate chart with ${bucketCount} journal ${entityPlural} buckets.`;
  if (highestLabel && highestRate) {
    return `${base} Highest win rate ${highestLabel} at ${highestRate}. Sample confidence ranks display order separately.`;
  }
  return `${base} Sample confidence ranks display order separately.`;
}

export function setupExpectancyAriaLabel(
  groupBy: SetupGroupBy,
  bucketCount: number,
  bestLabel: string | null,
  bestValue: string | null,
): string {
  const { entitySingular, entityPlural } = setupGroupCopy(groupBy);
  if (bucketCount === 0) {
    return `${entitySingular.charAt(0).toUpperCase()}${entitySingular.slice(1)} expectancy chart with no data`;
  }
  const base = `${entitySingular.charAt(0).toUpperCase()}${entitySingular.slice(1)} expectancy chart (mean net P&L per trade) with ${bucketCount} journal ${entityPlural} buckets.`;
  if (bestLabel && bestValue) {
    return `${base} Highest expectancy ${bestLabel} at ${bestValue}.`;
  }
  return base;
}
