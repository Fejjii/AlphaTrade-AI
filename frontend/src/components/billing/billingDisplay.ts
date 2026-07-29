import type { SubscriptionPlan, UsageExportResponse } from "@/lib/api/types";
import { formatCount, formatCurrency, humanizeToken } from "@/lib/format";

export function resolveBillingCurrencyCode(
  plans: readonly SubscriptionPlan[],
  currentPlanId: string,
): string | null {
  const code =
    plans.find((plan) => plan.plan_id === currentPlanId)?.price_currency ??
    plans[0]?.price_currency ??
    null;
  return code?.trim() ? code.trim() : null;
}

export function formatBillingProviderLabel(provider: string): string {
  if (provider === "mock") return "Simulation";
  if (provider === "stripe") return "Stripe";
  return humanizeToken(provider);
}

export function formatUsageExportSummary(
  exportResult: UsageExportResponse,
  currencyCode: string | null,
): {
  events: string;
  tokens: string;
  billingGradeCost: string;
  costBasisLabel: string;
} {
  return {
    events: formatCount(exportResult.total_events),
    tokens: formatCount(exportResult.total_tokens),
    billingGradeCost: formatCurrency(exportResult.billing_grade_cost, currencyCode),
    costBasisLabel: exportResult.cost_is_billing_grade
      ? "Provider-reported (billing-grade)"
      : "Includes estimates",
  };
}

export const ADMIN_ACCESS_TITLE = "Administrator access required";
