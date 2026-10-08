import { apiFetch } from "@/lib/api/client";

export type ManualDemoInput = {
  symbol: "BTCUSDT";
  side: "BUY" | "SELL";
  order_type: "MARKET";
  quantity: string;
  stop: string;
  target: string;
};
export type ManualDemoInstrument = {
  account_id: string;
  instrument: string;
  quantity_unit: "CONTRACTS";
  base_currency: "BTC";
  minimum_quantity: string;
  maximum_quantity: string;
  lot_increment: string;
  tick_size: string;
  contract_multiplier: string;
  minimum_notional: string;
  reference_price: string;
  observed_at: string;
};
export type ManualDemoPreview = {
  origin: "manual demo test";
  account_id: string;
  revision_id: string;
  content_hash: string;
  instrument: string;
  side: "BUY" | "SELL";
  order_type: "MARKET";
  quantity: string;
  quantity_unit: "CONTRACTS";
  base_quantity: string;
  reference_price: string;
  limit_price: null;
  entry_lower: string;
  entry_upper: string;
  stop: string;
  target: string;
  maximum_planned_loss: string;
  gross_reward_risk: string;
  valid_until: string;
  warnings: string[];
};
export type ManualDemoStatus = {
  origin: "manual demo test";
  revision_id: string;
  command_id: string;
  client_order_id: string;
  venue_order_id?: string | null;
  protection_order_ids?: string[];
  status: string;
  filled_quantity: string;
  remaining_quantity: string;
  average_fill_price: string | null;
  fees: string | null;
  protection: string;
  journal_trade_id: string | null;
  missing_evidence: string[];
  reconciliation_diagnostics?: {
    stage: string;
    reason_code: string;
    error_type: string;
    endpoint_name: string;
    http_status?: number | null;
    venue_error_code?: string | null;
    field_name?: string | null;
  }[];
};
export const manualDemo = {
  instrument: () => apiFetch<ManualDemoInstrument>("/execution/manual-demo/instrument", { auth: true }),
  preview: (body: ManualDemoInput) => apiFetch<ManualDemoPreview>("/execution/manual-demo/preview", { auth: true, method: "POST", body: JSON.stringify(body) }),
  confirm: (preview: ManualDemoPreview) => apiFetch<ManualDemoStatus>("/execution/manual-demo/confirm", { auth: true, method: "POST", body: JSON.stringify({ revision_id: preview.revision_id, content_hash: preview.content_hash, confirm: true, label: "manual demo test" }) }),
  reconcile: (command: string) => apiFetch<ManualDemoStatus>(`/execution/manual-demo/${encodeURIComponent(command)}/reconcile`, { auth: true, method: "POST" }),
  cancel: (command: string) => apiFetch<ManualDemoStatus>(`/execution/manual-demo/${encodeURIComponent(command)}/cancel`, { auth: true, method: "POST", body: JSON.stringify({ confirm: true }) }),
};
