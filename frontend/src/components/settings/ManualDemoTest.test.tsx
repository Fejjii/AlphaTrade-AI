import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
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
function enterPlan() {
  render(<ManualDemoTest />);
  fireEvent.click(screen.getByRole("button", { name: "Prepare manual demo test" }));
  for (const [label, value] of [["Quantity in contracts", "2"], ["Stop (USDT)", "99000"], ["Target (USDT)", "102000"]]) {
    fireEvent.change(screen.getByRole("textbox", { name: label }), { target: { value } });
  }
  fireEvent.click(screen.getByRole("button", { name: "Preview demo entry" }));
}
async function prepare() {
  enterPlan();
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

it("allows below-1R connectivity preview only with explicit exact confirmation", async () => {
  const connectivityPreview = { ...preview, gross_reward_risk: "0.375" };
  vi.mocked(manualDemo.preview).mockResolvedValueOnce(connectivityPreview);
  await prepare();
  expect(
    screen.getByText(
      /minimum 1R does not apply; excluded from strategy performance/,
    ),
  ).toBeInTheDocument();
  expect(screen.getByText(/gross reward\/risk: 0.38R/)).toBeInTheDocument();
  expect(manualDemo.preview).toHaveBeenCalledWith(
    expect.objectContaining({ order_type: "MARKET" }),
  );
  const button = screen.getByRole("button", {
    name: "Confirm and submit demo market order",
  });
  expect(button).toBeDisabled();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole("checkbox", {
      name: "I confirm this exact manual demo test plan.",
    }),
  );
  fireEvent.click(button);
  fireEvent.click(button);
  await screen.findByText("Manual demo test: filled protected");
  expect(manualDemo.confirm).toHaveBeenCalledExactlyOnceWith(
    connectivityPreview,
  );
});
it("shows calculated RR and precise blocking reason for a refused preview", async () => {
  vi.mocked(manualDemo.preview).mockRejectedValueOnce(
    new ApiError(
      "Manual demo maximum planned loss exceeds the per-trade risk limit.",
      403,
      {
        error: {
          code: "trading_policy_violation",
          details: {
            reason: "per_trade_risk_limit_exceeded",
            gross_reward_risk: "0.375",
            credentials: "private provider data",
          },
        },
      },
    ),
  );
  enterPlan();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent(
    "Manual demo maximum planned loss exceeds the per-trade risk limit.",
  );
  expect(alert).toHaveTextContent("Error code: trading_policy_violation");
  expect(alert).toHaveTextContent(
    "Blocking reason: per_trade_risk_limit_exceeded",
  );
  expect(alert).toHaveTextContent("Calculated gross reward/risk: 0.38R");
  expect(alert).not.toHaveTextContent("private provider data");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});
it("shows quote preflight stage and reason without copying raw venue details", async () => {
  vi.mocked(manualDemo.preview).mockRejectedValueOnce(
    new ApiError(
      "BloFin demo order book has no executable depth for this size within 10 bps.",
      403,
      {
        error: {
          code: "trading_policy_violation",
          details: {
            preflight: {
              stage: "quote",
              reason_code: "quote_depth_insufficient",
              raw_payload: "private venue data",
            },
            gross_reward_risk: "NaN",
          },
        },
      },
    ),
  );
  enterPlan();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Blocked stage: quote");
  expect(alert).toHaveTextContent("Blocking reason: quote_depth_insufficient");
  expect(alert).not.toHaveTextContent("private venue data");
  expect(alert).not.toHaveTextContent("NaN");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});
