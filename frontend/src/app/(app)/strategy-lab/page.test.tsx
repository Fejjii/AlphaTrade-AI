import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import StrategyLabPage from "@/app/(app)/strategy-lab/page";

afterEach(cleanup);

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: { items: [{ id: "1", name: "Pullback", setup_type: "htf_trend_pullback", current_version: 1 }], total: 1 },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("StrategyLabPage", () => {
  it("renders strategy lab", () => {
    render(<StrategyLabPage />);
    expect(screen.getByText("Strategy Lab")).toBeInTheDocument();
    expect(screen.getByText("Create strategy")).toBeInTheDocument();
    expect(screen.getByText("Pullback")).toBeInTheDocument();
  });

  it("shows a status badge and next action for each strategy", () => {
    render(<StrategyLabPage />);
    expect(screen.getByTestId("strategy-status-badge")).toHaveTextContent("Needs structure");
    expect(screen.getByTestId("strategy-next-action")).toHaveTextContent("Next:");
  });
});
