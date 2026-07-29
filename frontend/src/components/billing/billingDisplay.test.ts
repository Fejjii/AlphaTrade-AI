import { describe, expect, it } from "vitest";

import {
  formatUsageExportSummary,
  resolveBillingCurrencyCode,
} from "./billingDisplay";

describe("billingDisplay", () => {
  it("never invents currency when plan currency is missing", () => {
    const summary = formatUsageExportSummary(
      {
        batch_id: "b1",
        organization_id: "org-1",
        period_start: "2026-07-01",
        period_end: "2026-07-31",
        total_events: 12,
        total_tokens: 3400,
        provider_reported_cost: "0",
        estimated_cost: "1.25",
        billing_grade_cost: "1.25",
        cost_is_billing_grade: false,
        fallback_event_count: 0,
        line_items: [],
        provider: "mock",
        exported_at: "2026-07-29T00:00:00Z",
      },
      null,
    );

    expect(summary.billingGradeCost).toBe("1.25");
    expect(summary.billingGradeCost).not.toMatch(/[$£€]/);
    expect(summary.events).toBe("12");
    expect(summary.tokens).toBe("3,400");
  });

  it("formats export cost with backend currency when available", () => {
    const code = resolveBillingCurrencyCode(
      [
        {
          plan_id: "pro",
          name: "Pro",
          description: "",
          monthly_token_limit: 1,
          monthly_cost_limit: "10",
          daily_request_limit: 1,
          limit_agent_chat: 1,
          limit_rag_ingest: 1,
          limit_market_analyze: 1,
          limit_agent_narrative: 1,
          limit_paper_execution: 1,
          seat_limit: 1,
          price_display: "$10",
          price_currency: "usd",
        },
      ],
      "pro",
    );

    const summary = formatUsageExportSummary(
      {
        batch_id: "b1",
        organization_id: "org-1",
        period_start: "2026-07-01",
        period_end: "2026-07-31",
        total_events: 1,
        total_tokens: 10,
        provider_reported_cost: "0",
        estimated_cost: "2.5",
        billing_grade_cost: "2.50",
        cost_is_billing_grade: true,
        fallback_event_count: 0,
        line_items: [],
        provider: "stripe",
        exported_at: "2026-07-29T00:00:00Z",
      },
      code,
    );

    expect(summary.billingGradeCost).toMatch(/2\.50/);
    expect(summary.billingGradeCost).toMatch(/\$|USD/i);
  });
});
