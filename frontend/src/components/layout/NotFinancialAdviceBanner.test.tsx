import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NotFinancialAdviceBanner } from "@/components/layout/NotFinancialAdviceBanner";

describe("NotFinancialAdviceBanner", () => {
  it("renders not financial advice disclaimer", () => {
    render(<NotFinancialAdviceBanner />);
    expect(screen.getByTestId("not-financial-advice-disclaimer")).toHaveTextContent(
      /not financial advice/i,
    );
  });
});
