export type PlanSignalContext = {
  source: "tradingview" | "setup_review" | "alert";
  signalId?: string;
  alertId?: string;
};

export type PlanSignalContextLookup =
  | { status: "none" }
  | { status: "ready"; context: PlanSignalContext }
  | { status: "invalid"; message: string };

const VALID_PLAN_SOURCES = new Set(["tradingview", "setup_review", "alert"]);

export function buildPlanHref(context: PlanSignalContext): string {
  const params = new URLSearchParams();
  params.set("source", context.source);
  if (context.signalId) params.set("signal", context.signalId);
  if (context.alertId) params.set("alert", context.alertId);
  return `/workspace?${params.toString()}`;
}

/**
 * Parse Plan deep-link query params without silently dropping invalid context.
 * Returns `invalid` when any plan-related param is present but cannot be applied.
 */
export function lookupPlanSignalContext(
  searchParams: URLSearchParams | { get: (key: string) => string | null },
): PlanSignalContextLookup {
  const source = searchParams.get("source");
  const signalRaw = searchParams.get("signal");
  const alertRaw = searchParams.get("alert");
  const signalId = signalRaw || undefined;
  const alertId = alertRaw || undefined;

  if (!source && !signalId && !alertId) {
    return { status: "none" };
  }

  if (!source || !VALID_PLAN_SOURCES.has(source)) {
    return {
      status: "invalid",
      message: "Signal context could not be applied because the source is invalid or incomplete.",
    };
  }

  if (!signalId && !alertId) {
    return {
      status: "invalid",
      message: "Signal context could not be applied because no signal or alert identifier was provided.",
    };
  }

  return {
    status: "ready",
    context: {
      source: source as PlanSignalContext["source"],
      signalId,
      alertId,
    },
  };
}

export function parsePlanSignalContext(
  searchParams: URLSearchParams | { get: (key: string) => string | null },
): PlanSignalContext | null {
  const result = lookupPlanSignalContext(searchParams);
  return result.status === "ready" ? result.context : null;
}

export function evidenceHrefForPlanContext(context: PlanSignalContext): string {
  if (context.source === "tradingview" && context.signalId) {
    return `/tradingview-signals?signal=${context.signalId}`;
  }
  if (context.source === "setup_review") return "/alerts/review";
  if (context.source === "alert") return "/alerts";
  return "/tradingview-signals";
}
