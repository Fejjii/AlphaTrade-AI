import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CanonicalPaperPlanButton } from "./CanonicalPaperPlanButton";
import type { ApprovalRequest } from "@/lib/api/types";

const executePaperPlan = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    execution: {
      executePaperPlan: (...args: unknown[]) => executePaperPlan(...args),
      paperOrder: vi.fn(),
    },
  },
}));

const approval: ApprovalRequest = {
  id: "appr-1",
  proposal_id: "prop-1",
  plan_revision_id: "rev-1",
  organization_id: "org",
  user_id: "user",
  status: "approved",
  risk_level: "medium",
  confidence: 0.7,
  created_at: "2026-09-19T12:01:00.000Z",
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
};

describe("CanonicalPaperPlanButton", () => {
  afterEach(() => {
    cleanup();
    executePaperPlan.mockReset();
  });

  it("executes through POST /execution/paper-plan and never calls legacy paper", async () => {
    executePaperPlan.mockResolvedValue({
      replayed: false,
      outcome: "ALLOW",
      command_id: "cmd-1",
      canonical_payload_hash: "cd".repeat(32),
      receipt: {
        receipt_id: "rcpt-1",
        command_id: "cmd-1",
        organization_id: "org",
        account_id: "acct-1",
        created_at: "2026-09-19T12:10:00.000Z",
        outcome: "ALLOW",
      },
    });
    render(<CanonicalPaperPlanButton approval={approval} />);
    fireEvent.click(screen.getByTestId("execute-paper-plan-button"));
    await waitFor(() => {
      expect(executePaperPlan).toHaveBeenCalledWith(
        expect.objectContaining({
          account_id: "acct-1",
          authorization_id: "auth-1",
          revision_id: "rev-1",
        }),
      );
    });
    expect(screen.getByTestId("paper-plan-outcome")).toHaveTextContent("ALLOW");
  });
});
