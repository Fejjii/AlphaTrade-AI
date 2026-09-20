import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DecisionApprovalPage from "./page";
import type { ApprovalRequest, TradeProposal } from "@/lib/api/types";

const proposal: TradeProposal = {
  id: "prop-1",
  organization_id: "org",
  user_id: "user",
  strategy_id: "htf_trend_pullback",
  symbol: "BTCUSDT",
  timeframe: "1h",
  direction: "long",
  entry_price: "65000",
  position_size: "0.1",
  leverage: "1",
  exit: {
    invalidation: "64000",
    stop_loss: "64000",
    take_profits: [{ price: "67000", size_fraction: 1 }],
  },
  confidence: 0.7,
  risk_level: "medium",
  rationale: "Defined invalidation.",
  status: "pending_approval",
  approval_required: true,
  created_at: "2026-09-19T12:00:00.000Z",
};

const approval: ApprovalRequest = {
  id: "appr-1",
  proposal_id: "prop-1",
  organization_id: "org",
  user_id: "user",
  status: "pending",
  risk_level: "medium",
  confidence: 0.7,
  created_at: "2026-09-19T12:01:00.000Z",
};

vi.mock("next/navigation", () => ({
  useParams: () => ({ approvalId: "appr-1" }),
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchStatus: { active: false, execution_blocked: false },
  }),
  useSafetyPosture: () => ({
    executionMode: "paper",
    realTradingEnabled: false,
    postureKnown: true,
  }),
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/components/ProposalDetailPanel", () => ({
  PaperOrderButton: () => <button type="button">Create paper order (simulated)</button>,
}));

const workflowState = {
  data: {
    approval,
    proposal,
    can_execute_paper: false,
    block_reason: "pending",
  },
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => workflowState,
}));

vi.mock("@/lib/api", () => ({
  api: {
    approvals: {
      workflow: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn(),
    },
    execution: {
      executePaperPlan: vi.fn(),
      paperOrder: vi.fn(),
    },
  },
}));

describe("Paper approval page", () => {
  afterEach(() => {
    cleanup();
    workflowState.data = {
      approval,
      proposal,
      can_execute_paper: false,
      block_reason: "pending",
    };
  });

  it("requires typed confirmation and states that approval does not execute", () => {
    render(<DecisionApprovalPage />);
    expect(screen.getByTestId("approval-does-not-execute")).toHaveTextContent(
      /does not place a paper order/i,
    );
    expect(screen.getByTestId("trade-plan-view")).toHaveTextContent("BTCUSDT");
    const approveButton = screen.getByTestId("approve-paper-button");
    expect(approveButton).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/type approve paper/i), {
      target: { value: "approve paper" },
    });
    expect(approveButton).not.toBeDisabled();
    expect(screen.getByTestId("canonical-paper-plan-button")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create paper order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute live/i })).not.toBeInTheDocument();
  });

  it("keeps paper-plan execute available when workflow returns no compatibility proposal", () => {
    workflowState.data = {
      approval: {
        ...approval,
        status: "approved",
        plan_revision_id: "rev-1",
        authorization: {
          authorization_id: "auth-1",
          approval_request_id: "appr-1",
          organization_id: "org",
          user_id: "user",
          account_id: "acct-1",
          revision_id: "rev-1",
          plan_id: "plan-1",
          plan_content_hash: "ab".repeat(32),
          state: "AVAILABLE",
          expires_at: "2026-09-19T13:00:00.000Z",
        },
      },
      proposal: null,
      can_execute_paper: false,
      block_reason: "Canonical plans execute via EXECUTE_PAPER_PLAN, not the proposal workflow.",
    };
    render(<DecisionApprovalPage />);
    expect(screen.queryByTestId("trade-plan-view")).not.toBeInTheDocument();
    expect(screen.getByTestId("canonical-paper-plan-button")).toBeInTheDocument();
    expect(screen.getByTestId("execute-paper-plan-button")).toBeEnabled();
    expect(screen.queryByRole("button", { name: /create paper order/i })).not.toBeInTheDocument();
  });
});
