"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { QuotaPanel } from "@/components/usage/QuotaPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState, SuccessState } from "@/components/states";
import { useAsyncData } from "@/hooks/useAsyncData";
import { api, ApiError } from "@/lib/api";
import type { SubscriptionPlan, UsageExportResponse } from "@/lib/api/types";

export default function BillingPage() {
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
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

  const mockMode = data ? data.status.is_mock || !data.status.billing_enabled : true;
  const livePayments =
    data?.status.billing_enabled === true && data.status.live_checkout_available;

  async function runOwnerAction(action: () => Promise<void>) {
    setBusy(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await action();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Billing</h1>
        <p className="text-sm text-zinc-400">
          Subscription plans and usage export groundwork. Paper trading only — no live exchange
          execution.
        </p>
      </div>

      {mockMode ? (
        <div
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
          data-testid="billing-mock-badge"
        >
          Mock billing mode — no real payments. Enable{" "}
          <code className="rounded bg-zinc-900 px-1">BILLING_ENABLED=true</code> and Stripe keys
          for live checkout (staging/production only).
        </div>
      ) : livePayments ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
          Live billing provider configured. Checkout uses Stripe placeholder URLs until API wiring.
        </div>
      ) : null}

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} onRetry={() => void reload()} /> : null}
      {actionError ? <ErrorState message={actionError} /> : null}
      {actionMessage ? <SuccessState message={actionMessage} /> : null}

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
              <p>Provider: {data.status.provider}</p>
              <p>Billing enabled: {data.status.billing_enabled ? "yes" : "no"}</p>
              {data.status.customer ? (
                <p>Billing email: {data.status.customer.billing_email ?? "—"}</p>
              ) : (
                <p className="text-zinc-500">No billing customer yet (OWNER can create one).</p>
              )}
            </CardContent>
          </Card>

          <QuotaPanel quota={data.quota} />
          <p className="text-xs text-zinc-500">
            <Link href="/usage" className="text-emerald-400 hover:underline">
              View full usage dashboard
            </Link>{" "}
            for cost source labels and event history.
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
                      disabled={busy || mockMode}
                      title={
                        mockMode
                          ? "Mock checkout — billing disabled or mock provider"
                          : "OWNER only"
                      }
                      onClick={() =>
                        void runOwnerAction(async () => {
                          if (!data.status.customer) {
                            await api.billing.createCustomer({});
                          }
                          const checkout = await api.billing.checkout(plan.plan_id);
                          setActionMessage(
                            checkout.is_mock
                              ? `Mock checkout URL: ${checkout.checkout_url}`
                              : `Checkout started: ${checkout.checkout_url}`,
                          );
                        })
                      }
                    >
                      {mockMode ? "Mock checkout" : "Checkout"}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Account actions (OWNER)</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void runOwnerAction(async () => {
                    await api.billing.createCustomer({});
                    setActionMessage("Billing customer created.");
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
                onClick={() =>
                  void runOwnerAction(async () => {
                    const portal = await api.billing.portal();
                    setActionMessage(
                      portal.is_mock
                        ? `Mock portal: ${portal.portal_url}`
                        : `Portal: ${portal.portal_url}`,
                    );
                  })
                }
              >
                {mockMode ? "Mock customer portal" : "Customer portal"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void runOwnerAction(async () => {
                    const exported = await api.billing.exportUsage();
                    setExportResult(exported);
                    setActionMessage(
                      exported.cost_is_billing_grade
                        ? "Usage export complete (billing-grade costs)."
                        : "Usage export complete — includes non-billing-grade estimates.",
                    );
                  })
                }
              >
                Export usage (OWNER)
              </Button>
            </CardContent>
          </Card>

          {exportResult ? (
            <Card data-testid="usage-export-summary">
              <CardHeader>
                <CardTitle>Latest usage export</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-zinc-400">
                <p>Events: {exportResult.total_events}</p>
                <p>Tokens: {exportResult.total_tokens}</p>
                <p>Billing-grade cost: {exportResult.billing_grade_cost}</p>
                <p>
                  Billing-grade only: {exportResult.cost_is_billing_grade ? "yes" : "no (estimates included)"}
                </p>
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
