import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import BillingPage from "@/app/(app)/billing/page";

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: {
      status: {
        billing_enabled: false,
        provider: "mock",
        is_mock: true,
        live_checkout_available: false,
        current_plan_id: "free",
        customer: null,
        subscription: null,
      },
      plans: [
        {
          plan_id: "free",
          name: "Free",
          description: "Free tier",
          monthly_token_limit: 500000,
          monthly_cost_limit: "25.00",
          daily_request_limit: 2000,
          limit_agent_chat: 500,
          limit_rag_ingest: 100,
          limit_market_analyze: 300,
          limit_agent_narrative: 500,
          limit_paper_execution: 50,
          seat_limit: 3,
          price_display: "$0 / month",
          price_currency: "usd",
        },
        {
          plan_id: "pro",
          name: "Pro",
          description: "Pro tier",
          monthly_token_limit: 2000000,
          monthly_cost_limit: "100.00",
          daily_request_limit: 5000,
          limit_agent_chat: 2000,
          limit_rag_ingest: 500,
          limit_market_analyze: 1000,
          limit_agent_narrative: 2000,
          limit_paper_execution: 200,
          seat_limit: 10,
          price_display: "$49 / month (placeholder)",
          price_currency: "usd",
        },
      ],
      quota: {
        quota: {
          organization_id: "org-1",
          monthly_token_limit: 500000,
          monthly_cost_limit: "25.00",
          daily_request_limit: 2000,
          limit_agent_chat: 500,
          limit_rag_ingest: 100,
          limit_market_analyze: 300,
          limit_agent_narrative: 500,
          limit_paper_execution: 50,
          soft_warning_threshold: "0.80",
          hard_block_threshold: "1.00",
          plan_id: "free",
        },
        usage: {
          monthly_tokens_used: 0,
          monthly_tokens_limit: 500000,
          monthly_tokens_pct: 0,
          monthly_cost_used: "0",
          monthly_cost_limit: "25.00",
          monthly_cost_pct: 0,
          daily_requests_used: 0,
          daily_requests_limit: 2000,
          daily_requests_pct: 0,
          feature_usage: {},
        },
        soft_limit_reached: false,
        hard_limit_reached: false,
        warnings: [],
        blocked_features: [],
      },
    },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

afterEach(() => {
  cleanup();
});

describe("BillingPage", () => {
  it("renders billing page with current plan", () => {
    render(<BillingPage />);
    expect(screen.getByRole("heading", { name: /billing/i })).toBeInTheDocument();
    expect(screen.getByTestId("current-plan")).toHaveTextContent("free");
  });

  it("renders mock billing mode badge", () => {
    render(<BillingPage />);
    expect(screen.getByTestId("billing-mock-badge")).toBeInTheDocument();
  });

  it("renders available plans", () => {
    render(<BillingPage />);
    expect(screen.getByTestId("plan-free")).toBeInTheDocument();
    expect(screen.getByTestId("plan-pro")).toBeInTheDocument();
  });

  it("renders mock checkout buttons when billing disabled", () => {
    render(<BillingPage />);
    expect(screen.getAllByRole("button", { name: /mock checkout/i }).length).toBeGreaterThan(0);
  });

  it("renders usage quota panel", () => {
    render(<BillingPage />);
    expect(screen.getByText(/monthly tokens/i)).toBeInTheDocument();
  });
});
