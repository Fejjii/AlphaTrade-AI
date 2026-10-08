import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BloFinDemoAccountCard } from "./BloFinDemoAccountCard";
import {
  demoAccountApi,
  type DashboardDemoAccount,
} from "@/lib/api/dashboard-demo-account";

vi.mock("@/lib/api/dashboard-demo-account", () => ({
  demoAccountApi: { latest: vi.fn(), refresh: vi.fn() },
}));

const latest = vi.mocked(demoAccountApi.latest);
const refresh = vi.mocked(demoAccountApi.refresh);

function account(
  overrides: Partial<DashboardDemoAccount> = {},
): DashboardDemoAccount {
  return {
    venue: "BLOFIN_DEMO",
    read_only: true,
    status: "ok",
    can_refresh: true,
    snapshot_id: "fixture-snapshot",
    synced_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 300_000).toISOString(),
    balances: [{ asset: "USDT", total: "1000.25", available: "900.125" }],
    positions: [
      {
        symbol: "BTCUSDT",
        side: "long",
        contracts: "0.1",
        entry_price: "82894",
        mark_price: null,
        unrealized_pnl: null,
        leverage: "1",
      },
    ],
    balances_truncated: false,
    positions_truncated: false,
    position_count: 1,
    message: "Native demo account snapshot.",
    ...overrides,
  };
}

beforeEach(() => {
  latest.mockReset().mockResolvedValue(account());
  refresh.mockReset().mockResolvedValue(account());
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("BloFin demo Dashboard", () => {
  it("loads saved balances and native contracts with explicit venue and unknown metrics", async () => {
    render(<BloFinDemoAccountCard />);
    expect(await screen.findByText("USDT balance")).toBeInTheDocument();
    expect(screen.getByText(/0.1 contracts/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealized PnL —/)).toBeInTheDocument();
    expect(screen.getByText("BLOFIN_DEMO")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Exchange settings" }),
    ).toHaveAttribute("href", "/settings/exchange");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("retrieves native data only on explicit refresh and ignores repeated clicks", async () => {
    let resolve!: (data: DashboardDemoAccount) => void;
    refresh.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    render(<BloFinDemoAccountCard />);
    const button = await screen.findByRole("button", {
      name: "Refresh demo account",
    });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    expect(
      screen.getByText(/Showing the previous saved snapshot/),
    ).toBeInTheDocument();
    await act(async () =>
      resolve(account({ positions: [], position_count: 0 })),
    );
    expect(
      await screen.findByText("No native open positions at this snapshot."),
    ).toBeInTheDocument();
    expect(latest).toHaveBeenCalledTimes(1);
  });

  it("Dashboard refresh reloads saved evidence without requesting native sync", async () => {
    const view = render(<BloFinDemoAccountCard refreshKey={0} />);
    await screen.findByText("USDT balance");
    latest.mockResolvedValue(account({ status: "stale" }));
    view.rerender(<BloFinDemoAccountCard refreshKey={1} />);
    expect(await screen.findByText("Stale snapshot")).toBeInTheDocument();
    expect(latest).toHaveBeenCalledTimes(2);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("does not let an older saved read overwrite newer saved evidence", async () => {
    let resolveOld!: (data: DashboardDemoAccount) => void;
    latest.mockReturnValue(
      new Promise((done) => {
        resolveOld = done;
      }),
    );
    const view = render(<BloFinDemoAccountCard />);
    latest.mockResolvedValue(account({ positions: [], position_count: 0 }));
    view.rerender(<BloFinDemoAccountCard refreshKey={1} />);
    expect(
      await screen.findByText("No native open positions at this snapshot."),
    ).toBeInTheDocument();
    await act(async () => resolveOld(account({ status: "stale" })));
    expect(screen.getByText("Fresh snapshot")).toBeInTheDocument();
    expect(screen.queryByText(/0.1 contracts/)).not.toBeInTheDocument();
  });

  it("Dashboard reload cannot overtake a pending native refresh", async () => {
    let resolve!: (data: DashboardDemoAccount) => void;
    refresh.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const view = render(<BloFinDemoAccountCard />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Refresh demo account" }),
    );
    view.rerender(<BloFinDemoAccountCard refreshKey={1} />);
    expect(latest).toHaveBeenCalledTimes(1);
    await act(async () =>
      resolve(account({ positions: [], position_count: 0 })),
    );
    expect(
      await screen.findByText("No native open positions at this snapshot."),
    ).toBeInTheDocument();
  });

  it("keeps a failure explicit and clears successful values", async () => {
    render(<BloFinDemoAccountCard />);
    await screen.findByText("USDT balance");
    refresh.mockResolvedValue(
      account({
        status: "unavailable",
        balances: [],
        positions: [],
        position_count: null,
        message: "The latest demo account sync failed.",
      }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh demo account" }),
    );
    expect(
      await screen.findByText("The latest demo account sync failed."),
    ).toBeInTheDocument();
    expect(screen.queryByText("USDT balance")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/No native open positions/),
    ).not.toBeInTheDocument();
  });

  it("clears values on HTTP failure, uses safe error text and supports retry", async () => {
    render(<BloFinDemoAccountCard />);
    await screen.findByText("USDT balance");
    refresh.mockRejectedValue(new Error("opaque raw error"));
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh demo account" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "could not be loaded",
    );
    expect(screen.queryByText("USDT balance")).not.toBeInTheDocument();
    expect(screen.queryByText("opaque raw error")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry account" }));
    expect(await screen.findByText("USDT balance")).toBeInTheDocument();
  });

  it.each(["inactive", "not_synced"] as const)(
    "shows %s without empty account claims",
    async (status) => {
      latest.mockResolvedValue(
        account({
          status,
          positions: [],
          balances: [],
          position_count: null,
          message: "Configure or refresh demo account.",
          can_refresh: status !== "inactive",
        }),
      );
      render(<BloFinDemoAccountCard />);
      await screen.findByText("Configure or refresh demo account.");
      expect(
        screen.queryByText(/No native open positions/),
      ).not.toBeInTheDocument();
    },
  );

  it("hides native refresh for readers and labels an incomplete position list", async () => {
    latest.mockResolvedValue(
      account({
        can_refresh: false,
        positions_truncated: true,
        position_count: null,
      }),
    );
    render(<BloFinDemoAccountCard />);
    await screen.findByText("USDT balance");
    expect(
      screen.queryByRole("button", { name: "Refresh demo account" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Native open positions · at least 1/),
    ).toBeInTheDocument();
    expect(screen.getByText(/owner can refresh/)).toBeInTheDocument();
  });

  it("marks the snapshot stale when its freshness window expires while open", async () => {
    vi.useFakeTimers();
    latest.mockResolvedValue(
      account({ expires_at: new Date(Date.now() + 1000).toISOString() }),
    );
    render(<BloFinDemoAccountCard />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("Fresh snapshot")).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(1001);
    });
    expect(screen.getByText("Stale snapshot")).toBeInTheDocument();
    expect(latest).toHaveBeenCalledTimes(1);
    expect(refresh).not.toHaveBeenCalled();
  });
});
