"use client";

import BillingPage from "@/app/(app)/billing/page";
import UsagePage from "@/app/(app)/usage/page";

/**
 * Canonical Settings → Billing & Usage L2 section (AT-040 Phase B).
 * Preserves both billing and usage capabilities under one route.
 */
export default function SettingsBillingAndUsagePage() {
  return (
    <div className="space-y-10">
      <BillingPage />
      <section
        id="usage"
        data-testid="billing-usage-section"
        className="space-y-4 border-t border-border-subtle pt-8"
      >
        <UsagePage />
      </section>
    </div>
  );
}
