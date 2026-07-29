import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PositionsPage from "./page";
import type { PaginatedPositions, Position } from "@/lib/api/types";

const ENTRY_PRICE = "50637.87";

function makePosition(overrides: Partial<Position> = {}): Position {
  return {
    id: "pos-1",
    organization_id: "org-1",
    user_id: "user-1",
    symbol: "BTCUSDT",
    direction: "long",
    size: "0.25",
    entry_price: ENTRY_PRICE,
    leverage: "1",
    stop_loss: null,
    take_profits: [],
    liquidation_price: null,
    unrealized_pnl: "12.5",
    realized_pnl: "0",
    risk_state: {},
    status: "open",
    opened_at: "2026-07-27T10:00:00.000Z",
    closed_at: null,
    ...overrides,
  };
}

function paginated(items: Position[]): PaginatedPositions {
  return { items, total: items.length, limit: 50, offset: 0 };
}

const mockReload = vi.fn<() => Promise<void>>();
const mockClosePaper = vi.fn();
const mockList = vi.fn();

let asyncState: {
  data: PaginatedPositions | null;
  loading: boolean;
  error: string | null;
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: asyncState.data,
    loading: asyncState.loading,
    error: asyncState.error,
    reload: mockReload,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    positions: {
      list: (...args: unknown[]) => mockList(...args),
      closePaper: (...args: unknown[]) => mockClosePaper(...args),
    },
  },
}));

function renderWithOpenPosition(position: Position = makePosition()) {
  asyncState = { data: paginated([position]), loading: false, error: null };
  render(<PositionsPage />);
  return position;
}

function startCloseFlow(exitPrice?: string) {
  fireEvent.click(screen.getByTestId("close-paper-start"));
  if (exitPrice !== undefined) {
    fireEvent.change(screen.getByTestId("close-paper-exit-price"), {
      target: { value: exitPrice },
    });
  }
  fireEvent.click(screen.getByTestId("close-paper-review"));
}

describe("PositionsPage loading/error/empty honesty (FP2-002)", () => {
  beforeEach(() => {
    asyncState = { data: null, loading: true, error: null };
    mockReload.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders only the loading state while the request is unresolved", () => {
    asyncState = { data: null, loading: true, error: null };
    render(<PositionsPage />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No positions/i)).not.toBeInTheDocument();
  });

  it("renders only the error state when the request failed", () => {
    asyncState = { data: null, loading: false, error: "Positions source down" };
    render(<PositionsPage />);
    expect(screen.getByTestId("error-state")).toHaveTextContent("Positions source down");
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No positions/i)).not.toBeInTheDocument();
  });

  it("offers retry on failure and triggers a reload", () => {
    asyncState = { data: null, loading: false, error: "Positions source down" };
    render(<PositionsPage />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(mockReload).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state only after a successful empty response", () => {
    asyncState = { data: paginated([]), loading: false, error: null };
    render(<PositionsPage />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent(/No positions/i);
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
  });

  it("renders the populated list after a successful response", () => {
    asyncState = {
      data: paginated([
        makePosition(),
        makePosition({ id: "pos-2", symbol: "ETHUSDT", direction: "short" }),
      ]),
      loading: false,
      error: null,
    };
    render(<PositionsPage />);
    expect(screen.getByText(/BTCUSDT/)).toBeInTheDocument();
    expect(screen.getByText(/ETHUSDT/)).toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No positions/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-hub-safety")).not.toBeInTheDocument();
  });
});

describe("PositionsPage paper-close honesty (FP2-001)", () => {
  beforeEach(() => {
    asyncState = { data: null, loading: true, error: null };
    mockReload.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows the current entry price for context in the close panel", () => {
    renderWithOpenPosition();
    fireEvent.click(screen.getByTestId("close-paper-start"));
    expect(screen.getByTestId("close-paper-panel")).toHaveTextContent(/current entry price/i);
  });

  it("rejects a missing exit price and submits nothing", () => {
    renderWithOpenPosition();
    startCloseFlow();
    expect(screen.getByText(/positive number/i)).toBeInTheDocument();
    expect(screen.queryByTestId("close-paper-confirmation")).not.toBeInTheDocument();
    expect(mockClosePaper).not.toHaveBeenCalled();
  });

  it.each(["abc", "-5", "0", "1e5", "50,000"])(
    "rejects the invalid exit price %s and submits nothing",
    (value) => {
      renderWithOpenPosition();
      startCloseFlow(value);
      expect(screen.getByText(/positive number/i)).toBeInTheDocument();
      expect(screen.queryByTestId("close-paper-confirmation")).not.toBeInTheDocument();
      expect(mockClosePaper).not.toHaveBeenCalled();
    },
  );

  it("requires confirmation showing symbol, side, size and the entered exit price", () => {
    renderWithOpenPosition();
    startCloseFlow("51000.5");
    const confirmation = screen.getByTestId("close-paper-confirmation");
    expect(confirmation).toHaveTextContent("BTCUSDT");
    expect(confirmation).toHaveTextContent("LONG");
    expect(confirmation).toHaveTextContent("0.25");
    expect(confirmation).toHaveTextContent("51000.5");
    expect(mockClosePaper).not.toHaveBeenCalled();
  });

  it("submits exactly the entered exit price with an honest reason and reloads on success", async () => {
    mockClosePaper.mockResolvedValue(makePosition({ status: "closed" }));
    const position = renderWithOpenPosition();
    startCloseFlow("51000.5");
    fireEvent.click(screen.getByTestId("close-paper-confirm"));

    await waitFor(() => expect(mockReload).toHaveBeenCalledTimes(1));
    expect(mockClosePaper).toHaveBeenCalledTimes(1);
    expect(mockClosePaper).toHaveBeenCalledWith(position.id, {
      exit_price: "51000.5",
      reason: "Paper close at user-entered exit price",
    });
  });

  it("never submits the entry price or a literal fallback price", async () => {
    mockClosePaper.mockResolvedValue(makePosition({ status: "closed" }));
    renderWithOpenPosition();
    startCloseFlow("51000.5");
    fireEvent.click(screen.getByTestId("close-paper-confirm"));

    await waitFor(() => expect(mockClosePaper).toHaveBeenCalledTimes(1));
    for (const call of mockClosePaper.mock.calls) {
      const body = call[1] as { exit_price: string };
      expect(body.exit_price).toBe("51000.5");
      expect(body.exit_price).not.toBe(ENTRY_PRICE);
      expect(body.exit_price).not.toBe("1");
    }
  });

  it("shows API failure feedback, keeps the position open and does not reload", async () => {
    mockClosePaper.mockRejectedValue(new Error("Paper close rejected by risk engine"));
    renderWithOpenPosition();
    startCloseFlow("51000.5");
    fireEvent.click(screen.getByTestId("close-paper-confirm"));

    const alert = await screen.findByTestId("close-paper-error");
    expect(alert).toHaveTextContent("Paper close rejected by risk engine");
    expect(alert).toHaveTextContent(/remains open/i);
    expect(mockReload).not.toHaveBeenCalled();
    // The position card is still rendered with its confirmation panel intact.
    expect(screen.getByTestId("close-paper-confirmation")).toBeInTheDocument();
    expect(screen.getByText(/BTCUSDT · LONG/)).toBeInTheDocument();
  });

  it("prevents duplicate close submissions while a close is in flight", async () => {
    let resolveClose: (value: Position) => void = () => undefined;
    mockClosePaper.mockImplementation(
      () =>
        new Promise<Position>((resolve) => {
          resolveClose = resolve;
        }),
    );
    renderWithOpenPosition();
    startCloseFlow("51000.5");

    const confirmButton = screen.getByTestId("close-paper-confirm");
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);

    expect(mockClosePaper).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(confirmButton).toBeDisabled());

    resolveClose(makePosition({ status: "closed" }));
    await waitFor(() => expect(mockReload).toHaveBeenCalledTimes(1));
    expect(mockClosePaper).toHaveBeenCalledTimes(1);
  });
});
