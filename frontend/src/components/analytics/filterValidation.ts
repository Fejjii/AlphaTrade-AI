import type { JournalStatsParams, PaperPortfolioParams, PortfolioSourceFilter } from "@/lib/api/types";

import { isoDateOnly } from "./format";

export type AnalyticsTab = "overview" | "performance";

export type AnalyticsFilterState = {
  tab: AnalyticsTab;
  dateFrom: string | null;
  dateTo: string | null;
  symbol: string | null;
  timeframe: string | null;
  portfolioSource: PortfolioSourceFilter | null;
  ignoredParams: string[];
};

export type AnalyticsFilterParams = {
  journal: JournalStatsParams;
  portfolio: PaperPortfolioParams;
  state: AnalyticsFilterState;
};

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const MAX_SYMBOL_LENGTH = 30;
const MAX_TIMEFRAME_LENGTH = 8;

const VALID_TABS = new Set<AnalyticsTab>(["overview", "performance"]);
const VALID_PP_SOURCES = new Set<PortfolioSourceFilter>([
  "all",
  "proposal_flow",
  "paper_validation",
]);

const UNSUPPORTED_PARAM_KEYS = [
  "setup_id",
  "portfolio_setup",
  "min_sample",
  "rule_compliance",
] as const;

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

function parseTab(value: string | null): { tab: AnalyticsTab; ignored: boolean } {
  if (!value || value === "overview") return { tab: "overview", ignored: false };
  if (VALID_TABS.has(value as AnalyticsTab)) return { tab: value as AnalyticsTab, ignored: false };
  return { tab: "overview", ignored: true };
}

function toJournalDatetime(date: string, endOfDay: boolean): string {
  return endOfDay ? `${date}T23:59:59.999Z` : `${date}T00:00:00.000Z`;
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
  const sourceParam = searchParams.get("source");
  if (sourceParam) {
    if (tab !== "performance") {
      ignoredParams.push("source");
    } else if (VALID_PP_SOURCES.has(sourceParam as PortfolioSourceFilter)) {
      portfolioSource = sourceParam as PortfolioSourceFilter;
    } else {
      ignoredParams.push("source");
    }
  }

  for (const key of UNSUPPORTED_PARAM_KEYS) {
    if (searchParams.get(key)) ignoredParams.push(key);
  }

  return {
    tab,
    dateFrom,
    dateTo,
    symbol,
    timeframe,
    portfolioSource,
    ignoredParams: [...new Set(ignoredParams)],
  };
}

export function buildAnalyticsApiParams(state: AnalyticsFilterState): AnalyticsFilterParams {
  const journal: JournalStatsParams = { group_by: "overall" };
  const portfolio: PaperPortfolioParams = { timezone: "UTC" };

  if (state.dateFrom) {
    journal.date_from = toJournalDatetime(state.dateFrom, false);
    portfolio.start_date = state.dateFrom;
  }
  if (state.dateTo) {
    journal.date_to = toJournalDatetime(state.dateTo, true);
    portfolio.end_date = state.dateTo;
  }
  if (state.symbol) {
    journal.symbol = state.symbol;
    portfolio.symbol = state.symbol;
  }
  if (state.timeframe) {
    journal.timeframe = state.timeframe;
    portfolio.timeframe = state.timeframe;
  }
  if (
    state.tab === "performance" &&
    state.portfolioSource &&
    state.portfolioSource !== "all"
  ) {
    portfolio.source = state.portfolioSource;
  }

  return { journal, portfolio, state };
}

export function buildFilterKey(params: AnalyticsFilterParams): string {
  return JSON.stringify({ journal: params.journal, portfolio: params.portfolio });
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
  return parts.join(" · ");
}
