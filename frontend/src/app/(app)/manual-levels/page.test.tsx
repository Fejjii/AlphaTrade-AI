import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ManualLevelsPage from "@/app/(app)/manual-levels/page";

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: { items: [], total: 0 },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("ManualLevelsPage", () => {
  it("renders manual levels page", () => {
    render(<ManualLevelsPage />);
    expect(screen.getByText("Manual Levels")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Add level" })).toBeInTheDocument();
  });
});
