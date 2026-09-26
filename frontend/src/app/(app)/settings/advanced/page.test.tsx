import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AdvancedSettingsPage from "./page";

describe("Advanced settings directory", () => {
  it("keeps operational routes linked without making them primary navigation", () => {
    render(<AdvancedSettingsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Advanced" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Strategy Lab" })).toHaveAttribute("href", "/strategy-lab");
    expect(screen.getByRole("link", { name: "Watcher" })).toHaveAttribute("href", "/watcher");
    expect(screen.getByRole("link", { name: "Billing & Usage" })).toHaveAttribute(
      "href",
      "/settings/billing",
    );
    expect(screen.getByRole("link", { name: "Validate hub" })).toHaveAttribute(
      "href",
      "/paper-validation",
    );
  });
});
