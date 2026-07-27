import type {
  JournalStatsParams,
  JournalTradeSource,
  PaperPortfolioParams,
  PortfolioSourceFilter,
  SetupEvidenceParams,
} from "@/lib/api/types";

import { isoDateOnly } from "./format";

export type AnalyticsTab = "overview" | "performance" | "setups";

export type SetupGroupBy = "setup" | "setup_version" | "strategy";

export type AnalyticsFilterState = {
  tab: AnalyticsTab;
  dateFrom: string | null;
  dateTo: string | null;
  symbol: string | null;
  timeframe: string | null;
  portfolioSource: PortfolioSourceFilter | null;
  /** Journal trade source — Setups tab only; never sent to portfolio or setup-evidence. */
  journalSource: JournalTradeSource | null;
  /** Journal setup-definition UUID only — never a Portfolio setup identity. */
  setupId: string | null;
  userStrategyId: string | null;
  groupBy: SetupGroupBy;
  bucketOffset: number;
  ignoredParams: string[];
};

export type AnalyticsFilterParams = {
  journal: JournalStatsParams;
  portfolio: PaperPortfolioParams;
  state: AnalyticsFilterState;
};

export type SetupAnalyticsApiParams = {
  journal: JournalStatsParams;
  evidence: SetupEvidenceParams;
  state: AnalyticsFilterState;
};

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_SYMBOL_LENGTH = 30;
const MAX_TIMEFRAME_LENGTH = 8;
export const SETUP_BUCKET_PAGE_SIZE = 20;

const VALID_TABS = new Set<AnalyticsTab>(["overview", "performance", "setups"]);
const VALID_PP_SOURCES = new Set<PortfolioSourceFilter>([
  "all",
  "proposal_flow",
  "paper_validation",
]);
export const JOURNAL_TRADE_SOURCE_OPTIONS: JournalTradeSource[] = [
  "manual",
  "paper_execution",
  "paper_validation",
  "backtest",
  "imported",
  "system",
];
const VALID_JOURNAL_SOURCES = new Set<JournalTradeSource>(JOURNAL_TRADE_SOURCE_OPTIONS);
const VALID_SETUP_GROUP_BY = new Set<SetupGroupBy>(["setup", "setup_version", "strategy"]);

/** Params never accepted as Portfolio identities on Analytics (PR 2). */
const ALWAYS_UNSUPPORTED_PARAM_KEYS = ["portfolio_setup", "min_sample", "rule_compliance"] as const;

export function isValidIsoDate(value: string): boolean {
  if (!ISO_DATE_PATTERN.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  if (Number.isNaN(parsed.getTime())) return false;
  return isoDateOnly(parsed) === value;
}

export function isValidSymbol(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.length > 0 && trimmed.length <= MAX_SYMBOL_LENGTH;
}

export function isValidTimeframe(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.length > 0 && trimmed.length <= MAX_TIMEFRAME_LENGTH;
}

/** Journal setup-definition / strategy UUID validator — display names are never accepted. */
export function isValidUuid(value: string): boolean {
  return UUID_PATTERN.test(value.trim());
}

function parseTab(value: string | null): { tab: AnalyticsTab; ignored: boolean } {
  if (!value || value === "overview") return { tab: "overview", ignored: false };
  if (VALID_TABS.has(value as AnalyticsTab)) return { tab: value as AnalyticsTab, ignored: false };
  return { tab: "overview", ignored: true };
}

function toJournalDatetime(date: string, endOfDay: boolean): string {
  return endOfDay ? `${date}T23:59:59.999Z` : `${date}T00:00:00.000Z`;
}

function parseNonNegativeInt(value: string): number | null {
  if (!/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) return null;
  return parsed;
}

/** Parse URL search params into validated filter state. Invalid values are ignored, never sent to APIs. */
export function parseAnalyticsSearchParams(searchParams: URLSearchParams): AnalyticsFilterState {
  const ignoredParams: string[] = [];
  const tabParam = searchParams.get("tab");
  const { tab, ignored: tabIgnored } = parseTab(tabParam);
  if (tabIgnored && tabParam) ignoredParams.push("tab");

  let dateFrom: string | null = null;
  const rawDateFrom = searchParams.get("date_from");
  if (rawDateFrom) {
    if (isValidIsoDate(rawDateFrom)) dateFrom = rawDateFrom;
    else ignoredParams.push("date_from");
  }

  let dateTo: string | null = null;
  const rawDateTo = searchParams.get("date_to");
  if (rawDateTo) {
    if (isValidIsoDate(rawDateTo)) dateTo = rawDateTo;
    else ignoredParams.push("date_to");
  }

  if (dateFrom && dateTo && dateFrom > dateTo) {
    ignoredParams.push("date_from", "date_to");
    dateFrom = null;
    dateTo = null;
  }

  let symbol: string | null = null;
  const rawSymbol = searchParams.get("symbol");
  if (rawSymbol) {
    if (isValidSymbol(rawSymbol)) symbol = rawSymbol.trim();
    else ignoredParams.push("symbol");
  }

  let timeframe: string | null = null;
  const rawTimeframe = searchParams.get("timeframe");
  if (rawTimeframe) {
    if (isValidTimeframe(rawTimeframe)) timeframe = rawTimeframe.trim();
    else ignoredParams.push("timeframe");
  }

  let portfolioSource: PortfolioSourceFilter | null = null;
  let journalSource: JournalTradeSource | null = null;
  const sourceParam = searchParams.get("source");
  if (sourceParam) {
    if (tab === "performance") {
      if (VALID_PP_SOURCES.has(sourceParam as PortfolioSourceFilter)) {
        portfolioSource = sourceParam as PortfolioSourceFilter;
      } else {
        ignoredParams.push("source");
      }
    } else if (tab === "setups") {
      if (VALID_JOURNAL_SOURCES.has(sourceParam as JournalTradeSource)) {
        journalSource = sourceParam as JournalTradeSource;
      } else {
        ignoredParams.push("source");
      }
    } else {
      ignoredParams.push("source");
    }
  }

  let setupId: string | null = null;
  const rawSetupId = searchParams.get("setup_id");
  if (rawSetupId) {
    if (tab !== "setups") {
      ignoredParams.push("setup_id");
    } else if (isValidUuid(rawSetupId)) {
      setupId = rawSetupId.trim().toLowerCase();
    } else {
      ignoredParams.push("setup_id");
    }
  }

  let userStrategyId: string | null = null;
  const rawStrategyId = searchParams.get("user_strategy_id");
  if (rawStrategyId) {
    if (tab !== "setups") {
      ignoredParams.push("user_strategy_id");
    } else if (isValidUuid(rawStrategyId)) {
      userStrategyId = rawStrategyId.trim().toLowerCase();
    } else {
      ignoredParams.push("user_strategy_id");
    }
  }

  let groupBy: SetupGroupBy = "setup";
  const rawGroupBy = searchParams.get("group_by");
  if (rawGroupBy) {
    if (tab !== "setups") {
      ignoredParams.push("group_by");
    } else if (VALID_SETUP_GROUP_BY.has(rawGroupBy as SetupGroupBy)) {
      groupBy = rawGroupBy as SetupGroupBy;
    } else {
      ignoredParams.push("group_by");
    }
  }

  let bucketOffset = 0;
  const rawOffset = searchParams.get("offset");
  if (rawOffset) {
    if (tab !== "setups") {
      ignoredParams.push("offset");
    } else {
      const parsed = parseNonNegativeInt(rawOffset);
      if (parsed === null) ignoredParams.push("offset");
      else bucketOffset = parsed;
    }
  }

  for (const key of ALWAYS_UNSUPPORTED_PARAM_KEYS) {
    if (searchParams.get(key)) ignoredParams.push(key);
  }

  return {
    tab,
    dateFrom,
    dateTo,
    symbol,
    timeframe,
    portfolioSource,
    journalSource,
    setupId,
    userStrategyId,
    groupBy,
    bucketOffset,
    ignoredParams: [...new Set(ignoredParams)],
  };
}

function applySharedJournalFilters(
  journal: JournalStatsParams,
  state: AnalyticsFilterState,
): void {
  if (state.dateFrom) journal.date_from = toJournalDatetime(state.dateFrom, false);
  if (state.dateTo) journal.date_to = toJournalDatetime(state.dateTo, true);
  if (state.symbol) journal.symbol = state.symbol;
  if (state.timeframe) journal.timeframe = state.timeframe;
}

/**
 * Shared overview/performance API params.
 * Journal setup_id is intentionally never applied here and never sent to portfolio.
 */
export function buildAnalyticsApiParams(state: AnalyticsFilterState): AnalyticsFilterParams {
  const journal: JournalStatsParams = { group_by: "overall" };
  const portfolio: PaperPortfolioParams = { timezone: "UTC" };

  applySharedJournalFilters(journal, state);

  if (state.dateFrom) portfolio.start_date = state.dateFrom;
  if (state.dateTo) portfolio.end_date = state.dateTo;
  if (state.symbol) portfolio.symbol = state.symbol;
  if (state.timeframe) portfolio.timeframe = state.timeframe;
  if (
    state.tab === "performance" &&
    state.portfolioSource &&
    state.portfolioSource !== "all"
  ) {
    portfolio.source = state.portfolioSource;
  }

  return { journal, portfolio, state };
}

/** Setups-tab journal + evidence params. setup_id is journal UUID only. */
export function buildSetupAnalyticsApiParams(state: AnalyticsFilterState): SetupAnalyticsApiParams {
  const journal: JournalStatsParams = {
    group_by: state.groupBy,
    limit: SETUP_BUCKET_PAGE_SIZE,
    offset: state.bucketOffset,
  };
  applySharedJournalFilters(journal, state);
  if (state.setupId) journal.setup_id = state.setupId;
  if (state.userStrategyId) journal.user_strategy_id = state.userStrategyId;
  if (state.journalSource) journal.source = state.journalSource;

  const evidence: SetupEvidenceParams = {};
  if (state.setupId) evidence.setup_id = state.setupId;
  if (state.userStrategyId) evidence.strategy_id = state.userStrategyId;

  return { journal, evidence, state };
}

export function buildFilterKey(params: AnalyticsFilterParams): string {
  return JSON.stringify({ journal: params.journal, portfolio: params.portfolio });
}

export function buildSetupFilterKey(params: SetupAnalyticsApiParams): string {
  return JSON.stringify({ journal: params.journal, evidence: params.evidence });
}

export function formatAppliedFiltersSummary(state: AnalyticsFilterState): string {
  const parts: string[] = [];
  if (state.dateFrom || state.dateTo) {
    if (state.dateFrom && state.dateTo) parts.push(`dates ${state.dateFrom} → ${state.dateTo}`);
    else if (state.dateFrom) parts.push(`from ${state.dateFrom}`);
    else if (state.dateTo) parts.push(`until ${state.dateTo}`);
  } else {
    parts.push("dates all time");
  }
  if (state.symbol) parts.push(`symbol ${state.symbol}`);
  if (state.timeframe) parts.push(`timeframe ${state.timeframe}`);
  if (state.tab === "performance" && state.portfolioSource && state.portfolioSource !== "all") {
    parts.push(`source ${state.portfolioSource}`);
  }
  if (state.tab === "setups") {
    parts.push(`group ${state.groupBy}`);
    if (state.journalSource) parts.push(`source ${state.journalSource}`);
    if (state.setupId) parts.push(`setup_id ${state.setupId}`);
    if (state.userStrategyId) parts.push(`strategy ${state.userStrategyId}`);
  }
  return parts.join(" · ");
}
