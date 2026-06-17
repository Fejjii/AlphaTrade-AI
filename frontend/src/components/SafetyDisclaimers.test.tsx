import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SafetyDisclaimers } from "@/components/SafetyDisclaimers";

afterEach(cleanup);

describe("SafetyDisclaimers", () => {
  it("renders the consistent global disclaimers", () => {
    render(<SafetyDisclaimers />);
    const list = screen.getByTestId("safety-disclaimers");
    expect(list).toHaveTextContent("Not financial advice.");
    expect(list).toHaveTextContent("Paper trading only");
    expect(list).toHaveTextContent("Real trading is disabled.");
    expect(list).toHaveTextContent("Alerts do not execute trades.");
    expect(list).toHaveTextContent("AI explanations never override deterministic risk rules.");
  });
});
