import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { ManualDemoTest } from "./ManualDemoTest";
import { manualDemo, type ManualDemoInstrument, type ManualDemoPreview, type ManualDemoStatus } from "@/lib/api/manual-demo";

const preview: ManualDemoPreview = {
  origin: "manual demo test", account_id: "account", revision_id: "revision", content_hash: "a".repeat(64),
  instrument: "BTC-USDT", side: "BUY", order_type: "MARKET", quantity: "2", quantity_unit: "CONTRACTS",
  base_quantity: "0.002", reference_price: "100000", limit_price: null,
  entry_lower: "99900", entry_upper: "100100", stop: "99000", target: "102000",
  maximum_planned_loss: "2.6004", gross_reward_risk: "1.727", valid_until: "2026-10-07T12:00:00Z",
  warnings: ["Excluded from strategy validation."],
};
const instrument: ManualDemoInstrument = {
  account_id: "account", instrument: "BTC-USDT", quantity_unit: "CONTRACTS", base_currency: "BTC",
  minimum_quantity: "0.1", maximum_quantity: "1000000", lot_increment: "0.1", tick_size: "0.1",
  contract_multiplier: "0.001", minimum_notional: "5", reference_price: "100000", observed_at: "2026-10-08T12:00:00Z",
};
const status: ManualDemoStatus = {
  origin: "manual demo test", revision_id: "revision", command_id: "command", client_order_id: "durable-client",
  status: "filled_protected", filled_quantity: "2", remaining_quantity: "0", average_fill_price: "100001",
  fees: "0.02", protection: "verified", journal_trade_id: "journal", missing_evidence: ["Exit is not reconciled."],
};
beforeEach(() => {
  vi.spyOn(manualDemo, "history").mockResolvedValue({ items: [], total: 0, limit: 5, offset: 0 });
  vi.spyOn(manualDemo, "instrument").mockResolvedValue(instrument);
  vi.spyOn(manualDemo, "preview").mockResolvedValue(preview);
  vi.spyOn(manualDemo, "confirm").mockResolvedValue(status);
  vi.spyOn(manualDemo, "reconcile").mockResolvedValue(status);
  vi.spyOn(manualDemo, "cancel").mockResolvedValue(status);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
async function enterPlan() {
  render(<ManualDemoTest />);
  fireEvent.click(screen.getByRole("button", { name: "Prepare manual demo test" }));
  await screen.findByText(/Exchange minimum:/);
  for (const [label, value] of [["Quantity in contracts", "2"], ["Stop (USDT)", "99000"], ["Target (USDT)", "102000"]]) {
    fireEvent.change(screen.getByRole("textbox", { name: label }), { target: { value } });
  }
  fireEvent.click(screen.getByRole("button", { name: "Preview demo entry" }));
}
async function prepare() {
  await enterPlan();
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
  vi.mocked(manualDemo.confirm).mockResolvedValueOnce({ ...status, status: "partial_fill_protected_operator_hold", filled_quantity: "1", remaining_quantity: "1", can_cancel: true });
  await prepare();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm and submit demo market order" }));
  fireEvent.click(await screen.findByRole("button", { name: "Cancel unfilled entry remainder" }));
  await screen.findByText("Manual demo test: filled protected");
  expect(manualDemo.cancel).toHaveBeenCalledExactlyOnceWith("command");
  fireEvent.click(screen.getByRole("button", { name: "Refresh venue evidence" }));
  expect(manualDemo.reconcile).toHaveBeenCalledExactlyOnceWith("command");
});

it("shows safe native reconciliation diagnostics and refreshes only the same command", async () => {
  vi.mocked(manualDemo.confirm).mockResolvedValueOnce({
    ...status, status: "reconciliation_unavailable_operator_hold", protection: "unverified",
    filled_quantity: "0", average_fill_price: null, journal_trade_id: null,
    reconciliation_diagnostics: [{
      stage: "fill_lookup", reason_code: "venue_request_rejected", error_type: "ExchangeRequestError",
      endpoint_name: "GET /api/v1/trade/fills-history", http_status: 400, venue_error_code: "51000",
    }],
  });
  await prepare();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm and submit demo market order" }));
  const diagnostic = await screen.findByRole("alert");
  expect(diagnostic).toHaveTextContent("fill_lookup — venue_request_rejected");
  expect(diagnostic).toHaveTextContent("GET /api/v1/trade/fills-history; HTTP 400; venue code 51000");
  expect(diagnostic).toHaveTextContent("Do not resubmit");
  expect(screen.queryByRole("button", { name: "Confirm and submit demo market order" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Refresh venue evidence" }));
  await screen.findByText("Manual demo test: filled protected");
  expect(manualDemo.reconcile).toHaveBeenCalledExactlyOnceWith("command");
  expect(manualDemo.confirm).toHaveBeenCalledTimes(1);
  expect(manualDemo.preview).toHaveBeenCalledTimes(1);
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
  await enterPlan();
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
  await enterPlan();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Blocked stage: quote");
  expect(alert).toHaveTextContent("Blocking reason: quote_depth_insufficient");
  expect(alert).not.toHaveTextContent("private venue data");
  expect(alert).not.toHaveTextContent("NaN");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});

it("displays native contract metadata and BTC/notional estimates before preview", async () => {
  await enterPlan();
  expect(screen.getByText(/Exchange minimum: 0.1 contracts · lot increment: 0.1 contracts/)).toBeInTheDocument();
  expect(screen.getByText(/1 contract = 0.001 BTC/)).toBeInTheDocument();
  expect(screen.getByText(/BTC equivalent: 0.002 BTC · approximate notional: 200.00 USDT/)).toBeInTheDocument();
});

it.each([
  ["Quantity in contracts", "0.001", "Quantity is contracts, not BTC"],
  ["Quantity in contracts", "0.15", "increments of 0.1"],
  ["Stop (USDT)", "100010", "long needs stop below"],
  ["Target (USDT)", "100000", "long needs stop below"],
  ["Stop (USDT)", "99000.01", "price increment"],
])("rejects invalid %s %s before sending preview", async (label, value, message) => {
  await prepare();
  vi.mocked(manualDemo.preview).mockClear();
  fireEvent.change(screen.getByRole("textbox", { name: label }), { target: { value } });
  expect(screen.getByRole("alert")).toHaveTextContent(message);
  expect(screen.getByRole("button", { name: "Preview demo entry" })).toBeDisabled();
  expect(manualDemo.preview).not.toHaveBeenCalled();
  expect(manualDemo.confirm).not.toHaveBeenCalled();
});

it("keeps preview disabled and offers metadata refresh after an unknown account read", async () => {
  vi.mocked(manualDemo.instrument).mockRejectedValueOnce(new ApiError("Demo account state is unknown", 403, null));
  render(<ManualDemoTest />);
  fireEvent.click(screen.getByRole("button", { name: "Prepare manual demo test" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Preview demo entry" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Refresh instrument limits" }));
  await screen.findByText(/Exchange minimum:/);
  expect(manualDemo.instrument).toHaveBeenCalledTimes(2);
  expect(manualDemo.preview).not.toHaveBeenCalled();
});

it("permits a fresh preview only when the server proves confirmation never started", async () => {
  vi.mocked(manualDemo.confirm).mockRejectedValueOnce(new ApiError("Demo available funds changed", 403, {
    error: { details: { submission: "not_started", category: "manual_demo_limits" } },
  }));
  await prepare();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm and submit demo market order" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Policy group: manual demo limits");
  expect(screen.getByRole("button", { name: "Preview demo entry" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Recover this exact confirmation (no resend)" })).not.toBeInTheDocument();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});

it("retains exact recovery for post-submit policy errors without a not-started proof", async () => {
  vi.mocked(manualDemo.confirm).mockRejectedValueOnce(new ApiError("Fill fee conflicts; operator review", 403, {
    error: { details: { reason: "fill_conflict" } },
  }));
  await prepare();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Confirm and submit demo market order" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Recover this exact confirmation (no resend)" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Preview demo entry" })).not.toBeInTheDocument();
});

it("keeps form values stable while the preview request is pending", async () => {
  let finish!: (plan: ManualDemoPreview) => void;
  vi.mocked(manualDemo.preview).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  await enterPlan();
  expect(screen.getByRole("textbox", { name: "Quantity in contracts" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "Stop (USDT)" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "Target (USDT)" })).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "Demo side" })).toBeDisabled();
  finish(preview);
  await screen.findByText(/Maximum planned loss/);
  expect(screen.getByRole("textbox", { name: "Stop (USDT)" })).toBeEnabled();
});
