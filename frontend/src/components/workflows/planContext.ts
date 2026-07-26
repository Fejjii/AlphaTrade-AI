export type PlanSignalContext = {
  source: "tradingview" | "setup_review" | "alert";
  signalId?: string;
  alertId?: string;
};

export function buildPlanHref(context: PlanSignalContext): string {
  const params = new URLSearchParams();
  params.set("source", context.source);
  if (context.signalId) params.set("signal", context.signalId);
  if (context.alertId) params.set("alert", context.alertId);
  return `/workspace?${params.toString()}`;
}

export function parsePlanSignalContext(
  searchParams: URLSearchParams | { get: (key: string) => string | null },
): PlanSignalContext | null {
  const source = searchParams.get("source");
  if (source !== "tradingview" && source !== "setup_review" && source !== "alert") {
    return null;
  }
  const signalId = searchParams.get("signal") ?? undefined;
  const alertId = searchParams.get("alert") ?? undefined;
  if (!signalId && !alertId) return null;
  return {
    source,
    signalId: signalId || undefined,
    alertId: alertId || undefined,
  };
}

export function evidenceHrefForPlanContext(context: PlanSignalContext): string {
  if (context.source === "tradingview" && context.signalId) {
    return `/tradingview-signals?signal=${context.signalId}`;
  }
  if (context.source === "setup_review") return "/alerts/review";
  if (context.source === "alert") return "/alerts";
  return "/tradingview-signals";
}
