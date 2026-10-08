import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ManualDemoActivity } from "./ManualDemoActivity";
import { ManualDemoDetail } from "./ManualDemoDetail";
import { manualDemo, type ManualDemoAttempt } from "@/lib/api/manual-demo";
import { api } from "@/lib/api";

const original: ManualDemoAttempt = {
  command_id: "original-command",
  account_id: "account",
  account_name: "BloFin demo",
  venue: "BLOFIN_DEMO",
  origin: "manual_demo_test",
  attempted_at: "2026-10-08T12:56:20Z",
  submitted_at: "2026-10-08T12:56:28Z",
  symbol: "BTC-USDT",
  side: "BUY",
  requested_contracts: "0.1",
  base_quantity: "0.0001",
  stop: "82000",
  target: "83000",
  content_hash: "a".repeat(64),
  submission_outcome: "ALLOW",
  blocked_reason: null,
  detail_url: "/execution/manual-demo/original-command",
  evidence: {
    origin: "manual demo test",
    revision_id: "revision",
    command_id: "original-command",
    client_order_id: "client",
    venue_order_id: null,
    status: "reconciliation_unavailable_operator_hold",
    filled_quantity: "0",
    remaining_quantity: "0.1",
    average_fill_price: null,
    fees: null,
    protection: "unverified",
    journal_trade_id: null,
    missing_evidence: ["Refresh this exact command; do not resubmit."],
    execution_status: "submission_uncertain",
    position_status: "unknown",
    account_status: "unknown",
    reconciliation_freshness: "latest_read_failed",
    recovery_status: "unresolved",
    recovery_reason: "Unknown submission remains held.",
    can_reconcile: true,
    can_cancel: false,
    can_resolve: false,
  },
};
const blocked: ManualDemoAttempt = {
  ...original,
  command_id: "blocked-command",
  requested_contracts: "1",
  base_quantity: "0.001",
  submitted_at: null,
  submission_outcome: "BLOCKED",
  blocked_reason: "demo_account_already_claimed",
  detail_url: "/execution/manual-demo/blocked-command",
  evidence: {
    ...original.evidence,
    command_id: "blocked-command",
    execution_status: "blocked_before_submission",
    remaining_quantity: "1",
    can_cancel: false,
  },
};
beforeEach(() => {
  vi.spyOn(manualDemo, "history").mockResolvedValue({
    items: [blocked, original],
    total: 2,
    limit: 5,
    offset: 0,
  });
  vi.spyOn(manualDemo, "detail").mockResolvedValue(original);
  vi.spyOn(manualDemo, "reconcile").mockResolvedValue(original.evidence);
  vi.spyOn(manualDemo, "resolve").mockResolvedValue(original.evidence);
  vi.spyOn(manualDemo, "cancel").mockResolvedValue(original.evidence);
  vi.spyOn(manualDemo, "confirm").mockResolvedValue(original.evidence);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("history provides durable links for the original order and the separate blocked attempt", async () => {
  render(<ManualDemoActivity />);
  const link = await screen.findByRole("link", {
    name: /0.1 contracts \(0.0001 BTC\)/,
  });
  expect(link).toHaveAttribute(
    "href",
    "/execution/manual-demo/original-command",
  );
  expect(
    screen.getByRole("link", { name: /1 contracts \(0.001 BTC\)/ }),
  ).toHaveAttribute("href", "/execution/manual-demo/blocked-command");
  expect(
    screen.getByText("Blocked: demo account already claimed"),
  ).toBeInTheDocument();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});
it("reopens the command in a new component session without an original confirmation or Journal", async () => {
  for (let i = 0; i < 2; i++) {
    render(<ManualDemoDetail commandId="original-command" />);
    await screen.findByText("0.1 requested contracts = 0.0001 BTC");
    expect(screen.getByText("Journal: No fill projection")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Resolve verified lifecycle/ }),
    ).not.toBeInTheDocument();
    cleanup();
  }
  expect(manualDemo.detail).toHaveBeenCalledTimes(2);
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});
it("refreshes the selected command once even on a double click", async () => {
  render(<ManualDemoDetail commandId="original-command" />);
  const refresh = await screen.findByRole("button", {
    name: "Refresh native evidence for this attempt",
  });
  fireEvent.click(refresh);
  fireEvent.click(refresh);
  await vi.waitFor(() => expect(manualDemo.detail).toHaveBeenCalledTimes(2));
  expect(manualDemo.reconcile).toHaveBeenCalledExactlyOnceWith(
    "original-command",
  );
  expect(manualDemo.confirm).not.toHaveBeenCalled();
  expect(manualDemo.cancel).not.toHaveBeenCalled();
});
it("blocked attempts have no cancellation or invented submission", async () => {
  vi.mocked(manualDemo.detail).mockResolvedValue(blocked);
  render(<ManualDemoDetail commandId="blocked-command" />);
  await screen.findByText(
    "Blocked before submission: demo account already claimed",
  );
  expect(
    screen.queryByRole("button", { name: /Cancel/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/submission started: Not recorded/),
  ).toBeInTheDocument();
});
it("recovery requires explicit confirmation and preserves the selected identity", async () => {
  vi.mocked(manualDemo.detail).mockResolvedValue({
    ...original,
    evidence: {
      ...original.evidence,
      can_resolve: true,
      recovery_status: "eligible",
      position_status: "closed_verified",
      account_status: "flat",
      exit_quantity: "0.1",
      exit_price: "83000",
      protection: "missing",
      protection_history: [{ tpsl_id: "protect", state: "canceled" }],
    },
  });
  render(<ManualDemoDetail commandId="original-command" />);
  const resolve = await screen.findByRole("button", {
    name: "Resolve verified lifecycle",
  });
  expect(resolve).toBeDisabled();
  expect(
    screen.getByText(
      /A canceled protection record does not establish a position exit/,
    ),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(resolve);
  await vi.waitFor(() =>
    expect(manualDemo.resolve).toHaveBeenCalledExactlyOnceWith(
      "original-command",
    ),
  );
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});
it("exact-command Agent read is available before Journal creation and retains its conversation", async () => {
  const turn = vi
    .spyOn(api.agent, "turn")
    .mockResolvedValue({
      reply: "Native evidence for original-command is missing.",
      conversation_id: "conversation",
    } as Awaited<ReturnType<typeof api.agent.turn>>);
  render(<ManualDemoDetail commandId="original-command" />);
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Ask Agent about this exact attempt",
    }),
  );
  await screen.findByText("Native evidence for original-command is missing.");
  expect(turn).toHaveBeenNthCalledWith(1, {
    message: "Explain manual BloFin demo command original-command",
    action: {
      name: "paper_trade.read_recorded",
      arguments: {
        command_id: "original-command",
        execution_venue: "BLOFIN_DEMO",
        trade_origin: "manual_demo_test",
      },
    },
  });
  fireEvent.click(screen.getByRole("button", { name: "Explain that trade" }));
  await vi.waitFor(() =>
    expect(turn).toHaveBeenNthCalledWith(2, {
      message: "Explain that trade",
      conversation_id: "conversation",
    }),
  );
});
it("failed detail reads expose an actionable retry and no stale controls", async () => {
  vi.mocked(manualDemo.detail).mockRejectedValue(
    new Error("Command unavailable in this authenticated scope"),
  );
  render(<ManualDemoDetail commandId="original-command" />);
  await screen.findByRole("alert");
  expect(
    screen.getByRole("button", { name: "Retry stored detail" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Refresh native evidence/ }),
  ).not.toBeInTheDocument();
});
