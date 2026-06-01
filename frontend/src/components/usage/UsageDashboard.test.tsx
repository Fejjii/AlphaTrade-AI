import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CostSourceBadge } from "@/components/usage/CostSourceBadge";
import { QuotaPanel } from "@/components/usage/QuotaPanel";
import { UsageProviderTable } from "@/components/usage/UsageProviderTable";
import type { QuotaStatus, UsageSummary } from "@/lib/api/types";

const summary: UsageSummary = {
  event_count: 3,
  total_input_tokens: 1000,
  total_output_tokens: 200,
  total_tokens: 1200,
  total_provider_reported_cost: "0.05",
  total_estimated_cost: "0.10",
  total_cost: "0.15",
  billing_grade_cost: "0.05",
  cost_is_placeholder: true,
  total_tool_calls: 2,
  fallback_count: 1,
  cache_hit_count: 0,
};

const quota: QuotaStatus = {
  quota: {
    organization_id: "org-1",
    monthly_token_limit: 2000000,
    monthly_cost_limit: "100.00",
    daily_request_limit: 5000,
    limit_agent_chat: 2000,
    limit_rag_ingest: 500,
    limit_market_analyze: 1000,
    limit_agent_narrative: 2000,
    limit_paper_execution: 200,
    soft_warning_threshold: "0.80",
    hard_block_threshold: "1.00",
  },
  usage: {
    monthly_tokens_used: 1200,
    monthly_tokens_limit: 2000000,
    monthly_tokens_pct: 0.0006,
    monthly_cost_used: "0.15",
    monthly_cost_limit: "100.00",
    monthly_cost_pct: 0.0015,
    daily_requests_used: 3,
    daily_requests_limit: 5000,
    daily_requests_pct: 0.0006,
    feature_usage: { agent_chat: 2, rag_ingest: 1 },
  },
  soft_limit_reached: false,
  hard_limit_reached: false,
  warnings: [],
  blocked_features: [],
};

describe("usage dashboard components", () => {
  it("renders cost source label for estimates", () => {
    render(<CostSourceBadge costIsPlaceholder summary={summary} />);
    expect(screen.getByText(/not billing-grade/i)).toBeInTheDocument();
  });

  it("renders quota state", () => {
    render(<QuotaPanel quota={quota} />);
    expect(screen.getByText(/monthly tokens/i)).toBeInTheDocument();
    expect(screen.getByText(/1,200/)).toBeInTheDocument();
  });

  it("renders quota warning when soft limit reached", () => {
    render(
      <QuotaPanel
        quota={{
          ...quota,
          soft_limit_reached: true,
          warnings: ["Monthly token soft warning (85%)"],
        }}
      />,
    );
    expect(screen.getByText(/soft warning/i)).toBeInTheDocument();
  });

  it("renders provider usage table", () => {
    render(
      <UsageProviderTable
        rows={[
          {
            provider: "mock-llm",
            event_count: 2,
            total_tokens: 800,
            total_cost: "0.08",
            fallback_count: 1,
          },
        ]}
      />,
    );
    expect(screen.getByText("mock-llm")).toBeInTheDocument();
    expect(screen.getByText("800")).toBeInTheDocument();
  });
});
