"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { PortfolioSourceFilter } from "@/lib/api/types";

import { isoDateOnly, addDays } from "./format";
import {
  buildAnalyticsApiParams,
  parseAnalyticsSearchParams,
  type AnalyticsTab,
} from "./filterValidation";

export type { AnalyticsFilterParams, AnalyticsFilterState, AnalyticsTab } from "./filterValidation";

export type DatePreset = "7d" | "30d" | "90d" | "ytd" | "all";

const VALID_PRESETS = new Set<DatePreset>(["7d", "30d", "90d", "ytd", "all"]);

function buildHref(pathname: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function presetToRange(preset: DatePreset, now = new Date()): { from: string | null; to: string | null } {
  const today = isoDateOnly(now);
  switch (preset) {
    case "7d":
      return { from: isoDateOnly(addDays(now, -6)), to: today };
    case "30d":
      return { from: isoDateOnly(addDays(now, -29)), to: today };
    case "90d":
      return { from: isoDateOnly(addDays(now, -89)), to: today };
    case "ytd":
      return { from: `${now.getUTCFullYear()}-01-01`, to: today };
    case "all":
    default:
      return { from: null, to: null };
  }
}

export { buildAnalyticsApiParams, buildFilterKey, formatAppliedFiltersSummary } from "./filterValidation";

export function useAnalyticsFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const state = useMemo(
    () => parseAnalyticsSearchParams(searchParams),
    [searchParams],
  );

  const apiParams = useMemo(() => buildAnalyticsApiParams(state), [state]);

  const pushParams = useCallback(
    (mutator: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString());
      mutator(params);
      router.push(buildHref(pathname, params), { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const replaceParams = useCallback(
    (mutator: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString());
      mutator(params);
      router.replace(buildHref(pathname, params), { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const setTab = useCallback(
    (tab: AnalyticsTab) => {
      pushParams((params) => {
        if (tab === "overview") params.delete("tab");
        else params.set("tab", tab);
        if (tab !== "performance") params.delete("source");
      });
    },
    [pushParams],
  );

  const applyDraft = useCallback(
    (draft: {
      dateFrom?: string | null;
      dateTo?: string | null;
      symbol?: string | null;
      timeframe?: string | null;
      portfolioSource?: PortfolioSourceFilter | null;
    }) => {
      pushParams((params) => {
        const setOrDelete = (key: string, value: string | null | undefined) => {
          if (value) params.set(key, value);
          else params.delete(key);
        };
        if ("dateFrom" in draft) setOrDelete("date_from", draft.dateFrom);
        if ("dateTo" in draft) setOrDelete("date_to", draft.dateTo);
        if ("symbol" in draft) setOrDelete("symbol", draft.symbol);
        if ("timeframe" in draft) setOrDelete("timeframe", draft.timeframe);
        if ("portfolioSource" in draft) {
          if (draft.portfolioSource && draft.portfolioSource !== "all") {
            params.set("source", draft.portfolioSource);
          } else {
            params.delete("source");
          }
        }
      });
    },
    [pushParams],
  );

  const applyDatePreset = useCallback(
    (preset: DatePreset) => {
      if (!VALID_PRESETS.has(preset)) return;
      const range = presetToRange(preset);
      applyDraft({ dateFrom: range.from, dateTo: range.to });
    },
    [applyDraft],
  );

  const clearFilters = useCallback(() => {
    pushParams((params) => {
      params.delete("date_from");
      params.delete("date_to");
      params.delete("symbol");
      params.delete("timeframe");
      params.delete("source");
    });
  }, [pushParams]);

  const cleanupIgnoredParams = useCallback(() => {
    if (state.ignoredParams.length === 0) return;
    replaceParams((params) => {
      for (const key of state.ignoredParams) params.delete(key);
    });
  }, [replaceParams, state.ignoredParams]);

  return {
    state,
    apiParams,
    setTab,
    applyDraft,
    applyDatePreset,
    clearFilters,
    cleanupIgnoredParams,
  };
}
