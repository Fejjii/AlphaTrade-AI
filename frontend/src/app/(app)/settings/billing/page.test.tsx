import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SettingsBillingAndUsagePage from "./page";

vi.mock("@/components/billing/BillingPageView", () => ({
  BillingPageView: ({ embedded }: { embedded?: boolean }) => (
    <div data-testid="billing-embedded" data-embedded={embedded ? "true" : "false"}>
      Billing body
    </div>
  ),
}));

vi.mock("@/components/usage/UsagePageView", () => ({
  UsagePageView: ({
    embedded,
    omitQuota,
  }: {
    embedded?: boolean;
    omitQuota?: boolean;
  }) => (
    <div
      data-testid="usage-embedded"
      data-embedded={embedded ? "true" : "false"}
      data-omit-quota={omitQuota ? "true" : "false"}
    >
      Usage body
    </div>
  ),
}));

describe("Settings Billing & Usage page", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a single h1 via PageHeader and embeds billing and usage sections", () => {
    render(<SettingsBillingAndUsagePage />);

    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent("Billing & Usage");

    expect(screen.getByTestId("billing-embedded")).toHaveAttribute("data-embedded", "true");
    expect(screen.getByTestId("usage-embedded")).toHaveAttribute("data-embedded", "true");
    expect(screen.getByTestId("usage-embedded")).toHaveAttribute("data-omit-quota", "true");
    expect(screen.getByTestId("billing-usage-section")).toBeInTheDocument();
  });
});
