import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PreTradePage from "@/app/(app)/pre-trade/page";

describe("PreTradePage", () => {
  it("renders pre-trade panels", () => {
    render(<PreTradePage />);
    expect(screen.getByText("Pre-Trade Analysis")).toBeInTheDocument();
    expect(screen.getByText("Analyze setup")).toBeInTheDocument();
    expect(screen.getByText("Human vs system")).toBeInTheDocument();
  });
});
