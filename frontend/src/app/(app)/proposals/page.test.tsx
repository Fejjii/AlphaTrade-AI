import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProposalsPage from "./page";
import type { PaginatedTradeProposals, TradeProposal } from "@/lib/api/types";

const search = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => search,
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/components/ProposalDetailPanel", () => ({
  ProposalDetailPanel: ({ proposal }: { proposal: TradeProposal }) => (
    <div data-testid="proposal-detail-panel">Detail {proposal.symbol}</div>
  ),
}));

function makeProposal(overrides: Partial<TradeProposal> = {}): TradeProposal {
  return {
    id: "prop-1",
    organization_id: "org-1",
    user_id: "user-1",
    strategy_id: "htf_trend_pullback",
    symbol: "BTCUSDT",
    timeframe: "1h",
    direction: "long",
    entry_price: "50000",
    position_size: "0.1",
    leverage: "1",
    exit: {
      invalidation: "Below stop",
      stop_loss: "49000",
      take_profits: [{ price: "52000", size_fraction: 1 }],
    },
    confidence: 0.7,
    risk_level: "medium",
    rationale: "Pullback into support",
    status: "pending_approval",
    approval_required: true,
    created_at: "2026-07-27T10:00:00.000Z",
    ...overrides,
  };
}

function paginated(items: TradeProposal[]): PaginatedTradeProposals {
  return { items, total: items.length, limit: 50, offset: 0 };
}

const mockReload = vi.fn<() => Promise<void>>();
const mockList = vi.fn();
const mockWorkflow = vi.fn();

let listState: {
  data: PaginatedTradeProposals | null;
  loading: boolean;
  error: string | null;
};

let workflowState: {
  data: { proposal: TradeProposal; approval: null } | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: (loader: () => Promise<unknown>, deps: unknown[]) => {
    void loader;
    // Second call is the workflow loader (depends on selected id).
    if (Array.isArray(deps) && deps.length === 1 && deps[0] !== undefined) {
      return workflowState;
    }
    return {
      data: listState.data,
      loading: listState.loading,
      error: listState.error,
      reload: mockReload,
    };
  },
}));

vi.mock("@/lib/api", () => ({
  api: {
    proposals: {
      list: (...args: unknown[]) => mockList(...args),
      workflow: (...args: unknown[]) => mockWorkflow(...args),
    },
  },
}));

describe("ProposalsPage route honesty (FP2-129)", () => {
  beforeEach(() => {
    search.delete("id");
    listState = { data: null, loading: true, error: null };
    workflowState = {
      data: null,
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    mockReload.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders a single h1 and paper-adjacent kill-switch control", () => {
    listState = { data: paginated([]), loading: false, error: null };
    render(<ProposalsPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent("Trade Proposals");
    expect(screen.getByRole("button", { name: /kill switch/i })).toBeInTheDocument();
  });

  it("renders only the loading state while the request is unresolved", () => {
    listState = { data: null, loading: true, error: null };
    render(<ProposalsPage />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No trade proposals/i)).not.toBeInTheDocument();
  });

  it("renders only the error state with retry when the request failed", () => {
    listState = { data: null, loading: false, error: "Proposals source down" };
    render(<ProposalsPage />);
    expect(screen.getByTestId("error-state")).toHaveTextContent("Proposals source down");
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No trade proposals/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(mockReload).toHaveBeenCalledTimes(1);
  });

  it("renders the honest empty state only after a successful empty response", () => {
    listState = { data: paginated([]), loading: false, error: null };
    render(<ProposalsPage />);
    expect(screen.getByText(/No trade proposals/i)).toBeInTheDocument();
    expect(screen.getByText(/Select a proposal/i)).toBeInTheDocument();
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
  });

  it("renders successful content without fabricating empty or error states", () => {
    const proposal = makeProposal();
    listState = { data: paginated([proposal]), loading: false, error: null };
    workflowState = {
      data: { proposal, approval: null },
      loading: false,
      error: null,
      reload: vi.fn(),
    };
    render(<ProposalsPage />);
    expect(screen.getAllByText(/BTCUSDT/).length).toBeGreaterThan(0);
    expect(screen.getByTestId("proposal-detail-panel")).toHaveTextContent("BTCUSDT");
    expect(screen.queryByText(/No trade proposals/i)).not.toBeInTheDocument();
  });
});
