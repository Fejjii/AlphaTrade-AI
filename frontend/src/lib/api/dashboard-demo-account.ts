import { apiFetch } from "./client";

export interface DashboardDemoAccount {
  venue: "BLOFIN_DEMO";
  read_only: true;
  status:
    "ok" | "degraded" | "stale" | "unavailable" | "not_synced" | "inactive";
  can_refresh: boolean;
  snapshot_id: string | null;
  synced_at: string | null;
  expires_at: string | null;
  balances: Array<{ asset: string; total: string; available: string }>;
  positions: Array<{
    symbol: string;
    side: "long" | "short";
    contracts: string;
    entry_price: string | null;
    mark_price: string | null;
    unrealized_pnl: string | null;
    leverage: string | null;
  }>;
  balances_truncated: boolean;
  positions_truncated: boolean;
  position_count: number | null;
  message: string;
}

export const demoAccountApi = {
  latest: () =>
    apiFetch<DashboardDemoAccount>("/dashboard/demo-account", { auth: true }),
  refresh: () =>
    apiFetch<DashboardDemoAccount>("/dashboard/demo-account/refresh", {
      method: "POST",
      auth: true,
    }),
};
