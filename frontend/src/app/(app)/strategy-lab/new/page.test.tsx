import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import NewStrategyPage from "@/app/(app)/strategy-lab/new/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("NewStrategyPage", () => {
  it("renders strategy create form", () => {
    render(<NewStrategyPage />);
    expect(screen.getByRole("heading", { name: "Create strategy" })).toBeInTheDocument();
    expect(screen.getByLabelText("Strategy name")).toBeInTheDocument();
    expect(screen.getByText("Entry conditions (one per line)")).toBeInTheDocument();
  });
});
