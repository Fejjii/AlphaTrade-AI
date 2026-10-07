import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ManualDemoTest } from "./ManualDemoTest";
import { manualDemo, type ManualDemoPreview, type ManualDemoStatus } from "@/lib/api/manual-demo";

const preview: ManualDemoPreview = {
  origin: "manual demo test", account_id: "account", revision_id: "revision", content_hash: "a".repeat(64),
  instrument: "BTC-USDT", side: "BUY", order_type: "MARKET", quantity: "2", quantity_unit: "CONTRACTS",
  base_quantity: "0.002", reference_price: "100000", limit_price: null,
  entry_lower: "99900", entry_upper: "100100", stop: "99000", target: "102000",
  maximum_planned_loss: "2.6004", gross_reward_risk: "1.727", valid_until: "2026-10-07T12:00:00Z",
  warnings: ["Excluded from strategy validation."],
};
const status: ManualDemoStatus = {
  origin: "manual demo test", revision_id: "revision", command_id: "command", client_order_id: "durable-client",
  status: "filled_protected", filled_quantity: "2", remaining_quantity: "0", average_fill_price: "100001",
  fees: "0.02", protection: "verified", journal_trade_id: "journal", missing_evidence: ["Exit is not reconciled."],
};
beforeEach(() => {
  vi.spyOn(manualDemo, "preview").mockResolvedValue(preview);
  vi.spyOn(manualDemo, "confirm").mockResolvedValue(status);
  vi.spyOn(manualDemo, "reconcile").mockResolvedValue(status);
  vi.spyOn(manualDemo, "cancel").mockResolvedValue(status);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
async function prepare() {
  render(<ManualDemoTest />);
  fireEvent.click(screen.getByRole("button", { name: "Prepare manual demo test" }));
  for (const [label, value] of [["Quantity in contracts", "2"], ["Stop (USDT)", "99000"], ["Target (USDT)", "102000"]]) {
    fireEvent.change(screen.getByRole("textbox", { name: label }), { target: { value } });
  }
  fireEvent.click(screen.getByRole("button", { name: "Preview demo entry" }));
  await screen.findByText(/Maximum planned loss/);
}
it("confirmation is explicit and uses the displayed hash", async () => {
  await prepare();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
  const button = screen.getByRole("button", { name: "Confirm and submit demo market order" });
  expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(button);
  await screen.findByText("Manual demo test: filled protected");
  expect(manualDemo.confirm).toHaveBeenCalledExactlyOnceWith(preview);
  expect(screen.getByText(/Actual fill price: 100001/)).toBeInTheDocument();
  expect(screen.getByText("Exit is not reconciled.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm and submit demo market order" })).not.toBeInTheDocument();
});
it("editing invalidates the preview and prior confirmation", async () => {
  await prepare();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.change(screen.getByRole("textbox", { name: "Stop (USDT)" }), { target: { value: "99500" } });
  expect(screen.queryByText(/Maximum planned loss/)).not.toBeInTheDocument();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});
it("lost response only offers recovery of the same plan", async () => {
  vi.mocked(manualDemo.confirm).mockRejectedValueOnce(new Error("Response lost; order may exist"));
  await prepare();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm and submit demo market order" }));
  await screen.findByRole("alert");
  expect(screen.queryByRole("button", { name: "Preview demo entry" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Recover this exact confirmation (no resend)" }));
  await screen.findByText("Manual demo test: filled protected");
  expect(manualDemo.confirm).toHaveBeenNthCalledWith(2, preview);
});
it("partial fills expose actual facts and allow cancellation and reconciliation", async () => {
  vi.mocked(manualDemo.confirm).mockResolvedValueOnce({ ...status, status: "partial_fill_protected_operator_hold", filled_quantity: "1", remaining_quantity: "1" });
  await prepare();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm and submit demo market order" }));
  fireEvent.click(await screen.findByRole("button", { name: "Cancel unfilled entry remainder" }));
  await screen.findByText("Manual demo test: filled protected");
  expect(manualDemo.cancel).toHaveBeenCalledExactlyOnceWith("command");
  fireEvent.click(screen.getByRole("button", { name: "Refresh venue evidence" }));
  expect(manualDemo.reconcile).toHaveBeenCalledExactlyOnceWith("command");
});
