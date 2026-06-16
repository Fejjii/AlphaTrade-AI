import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import StrategyLabPage from "@/app/(app)/strategy-lab/page";

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
    expect(screen.getByText("Pullback")).toBeInTheDocument();
  });
});
