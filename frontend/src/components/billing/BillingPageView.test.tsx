import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BillingPageView } from "./BillingPageView";

const billingData = {
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
};

const liveBillingData = {
  ...billingData,
  status: {
    ...billingData.status,
    billing_enabled: true,
    is_mock: false,
    live_checkout_available: true,
    provider: "stripe",
    customer: {
      id: "cust-1",
      organization_id: "org-1",
      provider: "stripe",
      provider_customer_id: "cus_test",
      billing_email: "admin@example.com",
      status: "active",
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-01T00:00:00Z",
    },
  },
};

const asyncState: {
  data: typeof billingData | typeof liveBillingData | null;
  loading: boolean;
  error: string | null;
  reload: ReturnType<typeof vi.fn>;
} = {
  data: billingData,
  loading: false,
  error: null,
  reload: vi.fn(),
};

const checkoutMock = vi.fn();
const portalMock = vi.fn();
const exportUsageMock = vi.fn();
const createCustomerMock = vi.fn();

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({ ...asyncState }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    billing: {
      status: vi.fn(),
      plans: vi.fn(),
      checkout: (...args: unknown[]) => checkoutMock(...args),
      portal: (...args: unknown[]) => portalMock(...args),
      exportUsage: (...args: unknown[]) => exportUsageMock(...args),
      createCustomer: (...args: unknown[]) => createCustomerMock(...args),
    },
    usage: {
      quota: vi.fn(),
    },
  },
  ApiError: class ApiError extends Error {},
}));

beforeEach(() => {
  asyncState.data = billingData;
  asyncState.loading = false;
  asyncState.error = null;
  checkoutMock.mockReset();
  portalMock.mockReset();
  exportUsageMock.mockReset();
  createCustomerMock.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("BillingPageView product voice", () => {
  it("does not render raw OWNER, API wiring, or placeholder URL copy", () => {
    render(<BillingPageView embedded />);

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\bOWNER\b/i);
    expect(text).not.toContain("API wiring");
    expect(text).not.toContain("placeholder URL");
    expect(text).not.toContain("BILLING_ENABLED");
    expect(text).not.toContain("billing_enabled");
  });

  it("uses professional permission language on admin actions", () => {
    render(<BillingPageView embedded />);

    expect(screen.getByRole("heading", { name: "Account administration" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export usage" })).toHaveAttribute(
      "title",
      "Administrator access required",
    );
    expect(screen.getByTestId("billing-no-customer")).toHaveTextContent(
      /account administrator/i,
    );
  });

  it("keeps simulated billing honest in mock mode", () => {
    render(<BillingPageView embedded />);

    expect(screen.getByTestId("billing-mock-badge")).toHaveTextContent(/simulated billing/i);
    expect(screen.getByTestId("billing-mock-badge")).toHaveTextContent(
      /not enabled in this environment/i,
    );
    expect(screen.queryByTestId("billing-live-badge")).not.toBeInTheDocument();
  });

  it("shows live checkout availability without implementation jargon when enabled", () => {
    asyncState.data = liveBillingData;

    render(<BillingPageView embedded />);

    expect(screen.getByTestId("billing-live-badge")).toHaveTextContent(
      /live checkout is available/i,
    );
    expect(document.body.textContent).not.toContain("API wiring");
  });

  it("opens checkout via link instead of dumping the raw URL in success text", async () => {
    asyncState.data = liveBillingData;
    checkoutMock.mockResolvedValue({
      checkout_url: "https://checkout.example.com/session/abc123",
      session_id: "sess_1",
      is_mock: false,
    });

    render(<BillingPageView embedded />);

    fireEvent.click(screen.getByRole("button", { name: "Checkout" }));

    await waitFor(() => {
      expect(screen.getByTestId("billing-link-action")).toBeInTheDocument();
    });

    const openLink = screen.getByTestId("billing-link-open");
    expect(openLink).toHaveAttribute("href", "https://checkout.example.com/session/abc123");
    expect(screen.getByText("Checkout is ready.")).toBeInTheDocument();
    expect(screen.queryByText(/https:\/\/checkout\.example\.com/)).toBeNull();
  });

  it("labels mock checkout as a simulation with an actionable link", async () => {
    asyncState.data = liveBillingData;
    checkoutMock.mockResolvedValue({
      checkout_url: "https://mock.example.com/checkout",
      session_id: "mock_sess",
      is_mock: true,
    });

    render(<BillingPageView embedded />);

    fireEvent.click(screen.getByRole("button", { name: "Checkout" }));

    await waitFor(() => {
      expect(screen.getByTestId("billing-link-caption")).toHaveTextContent(/simulated checkout/i);
    });

    expect(screen.getByTestId("billing-link-open")).toHaveTextContent(/simulated checkout/i);
    expect(screen.queryByText(/https:\/\/mock\.example\.com/)).toBeNull();
  });

  it("opens customer portal via link and keeps mock portal explicitly simulated", async () => {
    asyncState.data = liveBillingData;
    portalMock.mockResolvedValue({
      portal_url: "https://billing.example.com/portal/session",
      is_mock: true,
    });

    render(<BillingPageView embedded />);

    fireEvent.click(screen.getByRole("button", { name: "Customer portal" }));

    await waitFor(() => {
      expect(screen.getByTestId("billing-link-open")).toHaveAttribute(
        "href",
        "https://billing.example.com/portal/session",
      );
    });

    expect(screen.getByTestId("billing-link-caption")).toHaveTextContent(/simulated customer portal/i);
    expect(screen.queryByText(/https:\/\/billing\.example\.com/)).toBeNull();
  });

  it("formats usage export summary with shared formatters and backend currency", async () => {
    asyncState.data = liveBillingData;
    exportUsageMock.mockResolvedValue({
      batch_id: "batch-1",
      organization_id: "org-1",
      period_start: "2026-07-01",
      period_end: "2026-07-31",
      total_events: 1200,
      total_tokens: 45000,
      provider_reported_cost: "0",
      estimated_cost: "12.34",
      billing_grade_cost: "12.34",
      cost_is_billing_grade: true,
      fallback_event_count: 0,
      line_items: [],
      provider: "stripe",
      exported_at: "2026-07-29T00:00:00Z",
    });

    render(<BillingPageView embedded />);

    fireEvent.click(screen.getByRole("button", { name: "Export usage" }));

    await waitFor(() => {
      expect(screen.getByTestId("usage-export-summary")).toBeInTheDocument();
    });

    expect(screen.getByTestId("usage-export-events")).toHaveTextContent("1,200");
    expect(screen.getByTestId("usage-export-tokens")).toHaveTextContent("45,000");
    expect(screen.getByTestId("usage-export-cost")).toHaveTextContent(/12\.34/);
    expect(screen.getByTestId("usage-export-cost").textContent).toMatch(/(\$|USD)/);
    expect(screen.getByTestId("usage-export-cost-basis")).toHaveTextContent(
      /provider-reported/i,
    );
  });

  it("does not invent currency on export when plans omit currency codes", async () => {
    asyncState.data = {
      ...liveBillingData,
      plans: [{ ...liveBillingData.plans[0], price_currency: "" }],
    };
    exportUsageMock.mockResolvedValue({
      batch_id: "batch-1",
      organization_id: "org-1",
      period_start: "2026-07-01",
      period_end: "2026-07-31",
      total_events: 3,
      total_tokens: 90,
      provider_reported_cost: "0",
      estimated_cost: "1.00",
      billing_grade_cost: "1.00",
      cost_is_billing_grade: false,
      fallback_event_count: 0,
      line_items: [],
      provider: "mock",
      exported_at: "2026-07-29T00:00:00Z",
    });

    render(<BillingPageView embedded />);

    fireEvent.click(screen.getByRole("button", { name: "Export usage" }));

    await waitFor(() => {
      expect(screen.getByTestId("usage-export-cost")).toBeInTheDocument();
    });

    const costText = screen.getByTestId("usage-export-cost").textContent ?? "";
    expect(costText).toContain("1.00");
    expect(costText).not.toMatch(/[$£€]/);
  });
});
