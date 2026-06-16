import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PreTradePage from "@/app/(app)/pre-trade/page";

vi.mock("@/lib/api", () => ({
  api: {
    pretrade: { analyze: vi.fn() },
    risk: { lossAcceptance: vi.fn() },
  },
}));

describe("PreTradePage", () => {
  it("renders loss acceptance section label", () => {
    render(<PreTradePage />);
    expect(screen.getByText("Pre-Trade Analysis")).toBeInTheDocument();
  });
});
