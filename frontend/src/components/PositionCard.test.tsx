import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { parseExitPrice, PositionCard } from "@/components/PositionCard";
import type { Position } from "@/lib/api/types";

function makePosition(overrides: Partial<Position> = {}): Position {
  return {
    id: "pos-1",
    organization_id: "org-1",
    user_id: "user-1",
    symbol: "BTCUSDT",
    direction: "long",
    size: "0.25",
    entry_price: "50637.87",
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

describe("parseExitPrice", () => {
  it("accepts plain positive decimals", () => {
    expect(parseExitPrice("51000.5")).toBe("51000.5");
    expect(parseExitPrice(" 42 ")).toBe("42");
  });

  it("rejects empty, non-positive, and scientific forms", () => {
    expect(parseExitPrice("")).toBeNull();
    expect(parseExitPrice("0")).toBeNull();
    expect(parseExitPrice("-1")).toBeNull();
    expect(parseExitPrice("1e5")).toBeNull();
  });
});

describe("PositionCard paper-close scrollIntoView guard", () => {
  const originalScrollIntoView = Element.prototype.scrollIntoView;

  afterEach(() => {
    Element.prototype.scrollIntoView = originalScrollIntoView;
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not throw when scrollIntoView is unavailable", () => {
    // jsdom often leaves scrollIntoView undefined; simulate that explicitly.
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: undefined,
    });

    render(<PositionCard position={makePosition()} onClosePaper={vi.fn()} />);
    expect(() => {
      fireEvent.click(screen.getByTestId("close-paper-start"));
    }).not.toThrow();
    expect(screen.getByTestId("close-paper-panel")).toBeInTheDocument();
    expect(screen.getByTestId("close-paper-exit-price")).toBeInTheDocument();
  });

  it("scrolls the close panel into view when scrollIntoView is available", () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      writable: true,
      value: scrollIntoView,
    });

    render(<PositionCard position={makePosition()} onClosePaper={vi.fn()} />);
    fireEvent.click(screen.getByTestId("close-paper-start"));

    expect(screen.getByTestId("close-paper-panel")).toBeInTheDocument();
    expect(scrollIntoView).toHaveBeenCalled();
    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "nearest",
      inline: "nearest",
    });
  });
});
