"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import {
  ADMIN_ACCESS_TITLE,
  formatBillingProviderLabel,
  formatUsageExportSummary,
  resolveBillingCurrencyCode,
} from "@/components/billing/billingDisplay";
import { QuotaPanel } from "@/components/usage/QuotaPanel";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState, SuccessState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api, ApiError } from "@/lib/api";
import type { SubscriptionPlan, UsageExportResponse } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type BillingLinkAction = {
  kind: "checkout" | "portal";
  url: string;
  isMock: boolean;
};

export function BillingPageView({ embedded = false }: { embedded?: boolean }) {
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [billingLink, setBillingLink] = useState<BillingLinkAction | null>(null);
  const [exportResult, setExportResult] = useState<UsageExportResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const loader = useCallback(async () => {
    const [status, plans, quota] = await Promise.all([
      api.billing.status(),
      api.billing.plans(),
      api.usage.quota(),
    ]);
    return { status, plans, quota };
  }, []);

  const { data, loading, error, reload } = useAsyncData(loader, []);

  const currencyCode = useMemo(
    () => (data ? resolveBillingCurrencyCode(data.plans, data.status.current_plan_id) : null),
    [data],
  );

  const exportSummary = useMemo(
    () => (exportResult ? formatUsageExportSummary(exportResult, currencyCode) : null),
    [currencyCode, exportResult],
  );

  // Tri-state billing mode (FP2-103): unknown until the status is verified.
  const mockMode: boolean | null = data
    ? data.status.is_mock || !data.status.billing_enabled
    : null;
  const livePayments =
    data?.status.billing_enabled === true && data.status.live_checkout_available;

  async function runAdminAction(action: () => Promise<void>) {
    setBusy(true);
    setActionError(null);
    setActionMessage(null);
    setBillingLink(null);
    try {
      await action();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  function adminActionTitle(unavailableReason?: string): string | undefined {
    if (unavailableReason) return unavailableReason;
    if (mockMode === true) {
      return "Live checkout is not available in this environment.";
    }
    return ADMIN_ACCESS_TITLE;
  }

  return (
    <div className="space-y-6">
      {embedded ? null : (
        <div>
          <h1 className="text-2xl font-semibold">Billing</h1>
          <p className="text-sm text-zinc-400">
            Subscription plans and usage export groundwork. Paper trading only — no live exchange
            execution.
          </p>
        </div>
      )}

      {mockMode === true ? (
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
          data-testid="billing-mock-badge"
        >
          Simulated billing — no real payments. Live checkout is not enabled in this environment.
        </div>
      ) : mockMode === false && livePayments ? (
        <div
          className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100"
          data-testid="billing-live-badge"
        >
          Live checkout is available for this organization.
        </div>
      ) : null}

      {loading ? <LoadingState /> : null}
      {error ? (
        <>
          <p
            className="text-sm text-amber-500/90"
            data-testid="billing-status-unavailable"
            role="status"
          >
            Billing status unavailable — the billing mode has not been verified.
          </p>
          <ErrorState message={error} onRetry={() => void reload()} />
        </>
      ) : null}
      {actionError ? <ErrorState message={actionError} /> : null}
      {actionMessage ? <SuccessState message={actionMessage} /> : null}

      {billingLink ? (
        <Card data-testid="billing-link-action">
          <CardHeader>
            <CardTitle className="text-base">
              {billingLink.kind === "checkout" ? "Checkout" : "Customer portal"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-zinc-300">
            <p data-testid="billing-link-caption">
              {billingLink.isMock
                ? billingLink.kind === "checkout"
                  ? "Simulated checkout — no payment will be processed."
                  : "Simulated customer portal — for demonstration only."
                : billingLink.kind === "checkout"
                  ? "Your secure checkout session is ready."
                  : "Your billing portal session is ready."}
            </p>
            <Link
              href={billingLink.url}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="billing-link-open"
              className={cn(buttonVariants({ variant: "secondary" }))}
            >
              {billingLink.isMock
                ? billingLink.kind === "checkout"
                  ? "Open simulated checkout"
                  : "Open simulated portal"
                : billingLink.kind === "checkout"
                  ? "Open checkout"
                  : "Open customer portal"}
            </Link>
          </CardContent>
        </Card>
      ) : null}

      {data ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Current plan</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-zinc-300">
              <p>
                Plan:{" "}
                <span className="font-medium text-zinc-100" data-testid="current-plan">
                  {data.status.current_plan_id}
                </span>
              </p>
              <p>
                Billing provider: {formatBillingProviderLabel(data.status.provider)}
              </p>
              <p>
                Live checkout:{" "}
                {data.status.live_checkout_available ? "Available" : "Unavailable"}
              </p>
              {data.status.customer ? (
                <p>Billing email: {data.status.customer.billing_email ?? "—"}</p>
              ) : (
                <p className="text-zinc-500" data-testid="billing-no-customer">
                  No billing customer on file. An account administrator can add billing details.
                </p>
              )}
            </CardContent>
          </Card>

          <QuotaPanel quota={data.quota} currencyCode={currencyCode} />
          <p className="text-xs text-zinc-500">
            <a href="#usage" className="text-emerald-400 hover:underline">
              View usage details
            </a>{" "}
            in the Billing &amp; Usage section below (when opened from Settings).
          </p>

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Available plans</h2>
            <div className="grid gap-4 md:grid-cols-3">
              {data.plans.map((plan: SubscriptionPlan) => (
                <Card key={plan.plan_id} data-testid={`plan-${plan.plan_id}`}>
                  <CardHeader>
                    <CardTitle className="text-base">{plan.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-zinc-400">
                    <p>{plan.description}</p>
                    <p>{plan.price_display}</p>
                    <p>{plan.monthly_token_limit.toLocaleString()} tokens / month</p>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={busy || mockMode === true}
                      title={adminActionTitle()}
                      onClick={() =>
                        void runAdminAction(async () => {
                          if (!data.status.customer) {
                            await api.billing.createCustomer({});
                          }
                          const checkout = await api.billing.checkout(plan.plan_id);
                          setBillingLink({
                            kind: "checkout",
                            url: checkout.checkout_url,
                            isMock: checkout.is_mock,
                          });
                          setActionMessage(
                            checkout.is_mock
                              ? "Simulated checkout is ready — no payment will be processed."
                              : "Checkout is ready.",
                          );
                        })
                      }
                    >
                      {mockMode === true ? "Simulated checkout" : "Checkout"}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Account administration</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                title={ADMIN_ACCESS_TITLE}
                onClick={() =>
                  void runAdminAction(async () => {
                    await api.billing.createCustomer({});
                    setActionMessage("Billing customer profile created.");
                    await reload();
                  })
                }
              >
                Create billing customer
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy || !data.status.customer}
                title={
                  !data.status.customer
                    ? "Add a billing customer before opening the portal."
                    : adminActionTitle()
                }
                onClick={() =>
                  void runAdminAction(async () => {
                    const portal = await api.billing.portal();
                    setBillingLink({
                      kind: "portal",
                      url: portal.portal_url,
                      isMock: portal.is_mock,
                    });
                    setActionMessage(
                      portal.is_mock
                        ? "Simulated customer portal is ready — for demonstration only."
                        : "Customer portal is ready.",
                    );
                  })
                }
              >
                {mockMode === true ? "Simulated customer portal" : "Customer portal"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                title={ADMIN_ACCESS_TITLE}
                onClick={() =>
                  void runAdminAction(async () => {
                    const exported = await api.billing.exportUsage();
                    setExportResult(exported);
                    setActionMessage(
                      exported.cost_is_billing_grade
                        ? "Usage export complete — billing-grade costs included."
                        : "Usage export complete — includes estimated costs.",
                    );
                  })
                }
              >
                Export usage
              </Button>
            </CardContent>
          </Card>

          {exportResult && exportSummary ? (
            <Card data-testid="usage-export-summary">
              <CardHeader>
                <CardTitle>Latest usage export</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1 text-sm text-zinc-400">
                <p data-testid="usage-export-events">Events: {exportSummary.events}</p>
                <p data-testid="usage-export-tokens">Tokens: {exportSummary.tokens}</p>
                <p data-testid="usage-export-cost">
                  Billing-grade cost: {exportSummary.billingGradeCost}
                </p>
                <p data-testid="usage-export-cost-basis">
                  Cost basis: {exportSummary.costBasisLabel}
                </p>
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
