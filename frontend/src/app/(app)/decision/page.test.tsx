import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DecisionHubPage from "./page";
import type { DecisionQueueSnapshot } from "@/lib/canonical-decision/types";

const safetyPosture = {
  executionMode: "paper" as string | null,
  realTradingEnabled: false as boolean | null,
  providerMode: "fallback",
  postureKnown: true,
};

vi.mock("next/navigation", () => ({
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/decision",
}));

vi.mock("@/contexts/AppContext", () => ({
  useAppContext: () => ({
    killSwitchActive: false,
    killSwitchStatus: { active: false, execution_blocked: false },
  }),
  useSafetyPosture: () => safetyPosture,
}));

vi.mock("@/components/KillSwitchButton", () => ({
  KillSwitchButton: () => <button type="button">Kill switch</button>,
}));

vi.mock("@/components/ProposalDetailPanel", () => ({
  PaperOrderButton: () => <button type="button">Create paper order (simulated)</button>,
}));

const snapshot: DecisionQueueSnapshot = {
  cases: [
    {
      id: "proposal:prop-1",
      kind: "legacy_proposal",
      stage: "approval",
      symbol: "BTCUSDT",
      direction: "long",
      timeframe: "1h",
      title: "BTCUSDT long",
      summary: "approval · blocked",
      href: "/decision/approvals/appr-1",
      createdAt: "2026-09-19T12:00:00.000Z",
      candidate: {
        authority: "compatibility_projection",
        caseId: "proposal:prop-1",
        sourceId: "prop-1",
        sourceKind: "legacy_proposal",
        lifecycleState: "plan_created",
        symbol: "BTCUSDT",
        timeframe: "1h",
        direction: "long",
        setupLabel: "htf_trend_pullback",
        thesis: "test",
        entryCriteria: "Entry 65000",
        invalidation: "64000",
        confidence: 0.7,
        evidence: [],
        strategyId: "htf_trend_pullback",
        createdAt: "2026-09-19T12:00:00.000Z",
        legacyHref: "/proposals?id=prop-1",
        marketQuality: {
          authority: "compatibility_projection",
          grade: "watch",
          setupState: "unknown",
          dataQuality: null,
          confidence: 0.7,
          confidencePenaltyApplied: false,
          symbol: "BTCUSDT",
          timeframe: "1h",
          direction: "long",
          evidence: [],
          summary: "Proposal-derived",
          doesNotGrantEligibility: true,
        },
        eligibility: {
          authority: "compatibility_projection",
          state: "blocked",
          paperActionable: false,
          liveExecutable: false,
          reasonCodes: ["blocked_human_approval_required"],
          explanations: [
            {
              code: "blocked_human_approval_required",
              title: "Human approval required",
              detail: "A human must approve the exact paper plan.",
              domain: "approval",
              blocking: true,
            },
          ],
          checkedAt: null,
          validUntil: null,
          killSwitchActive: false,
          humanApprovalSatisfied: false,
        },
      },
      tradePlan: null,
      approval: null,
      execution: null,
      outcome: null,
      learning: null,
    },
  ],
  stageCounts: {
    market_assessment: 0,
    candidate: 0,
    eligibility: 0,
    trade_plan: 0,
    approval: 1,
    paper_execution: 0,
    outcome: 0,
    learning: 0,
  },
  missingBindings: ["canonical-candidates"],
};

vi.mock("@/lib/canonical-decision/compose", async () => {
  const actual = await vi.importActual<typeof import("@/lib/canonical-decision/compose")>(
    "@/lib/canonical-decision/compose",
  );
  return {
    ...actual,
    composeDecisionCases: () => snapshot,
  };
});

let asyncState = {
  data: {
    canonicalCandidates: { data: { items: [] }, available: true },
    candidates: { data: { items: [] }, available: true },
    proposals: { data: { items: [] }, available: true },
    approvals: { data: { items: [] }, available: true },
    orders: { data: { items: [] }, available: true },
    journals: { data: { items: [] }, available: true },
    lessons: { data: { items: [] }, available: true },
  },
  loading: false,
  error: null as string | null,
  reload: vi.fn(),
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => asyncState,
}));

describe("Decision hub", () => {
  beforeEach(() => {
    asyncState = { ...asyncState, loading: false, error: null };
  });
  afterEach(() => cleanup());

  it("renders the paper decision spine and forbids live execution copy", () => {
    render(<DecisionHubPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Decision" })).toBeInTheDocument();
    expect(screen.getByTestId("decision-stepper")).toBeInTheDocument();
    expect(screen.getByTestId("decision-safety-rail")).toBeInTheDocument();
    expect(screen.getByTestId("decision-human-approval-copy")).toHaveTextContent(
      /human approval is mandatory/i,
    );
    expect(screen.getByTestId("decision-case-card")).toHaveTextContent("BTCUSDT long");
    expect(screen.queryByRole("button", { name: /place real order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute live/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("binding-canonical-candidates")).not.toBeInTheDocument();
    expect(screen.getByTestId("binding-paper-validation-candidates")).toHaveTextContent("partial");
    expect(screen.getByTestId("binding-legacy-paper-execution")).toHaveTextContent("partial");
  });

  it("shows loading state", () => {
    asyncState = { ...asyncState, loading: true, data: asyncState.data };
    render(<DecisionHubPage />);
    expect(screen.getByText(/loading decision queue/i)).toBeInTheDocument();
  });
});
