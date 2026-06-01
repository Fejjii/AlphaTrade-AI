import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProviderStatusCard } from "@/components/ProviderStatusCard";
import { StatusBadge } from "@/components/StatusBadge";

describe("StatusBadge", () => {
  it("renders paper mode label", () => {
    render(<StatusBadge label="PAPER mode" tone="paper" />);
    expect(screen.getByText("PAPER mode")).toBeInTheDocument();
  });
});

describe("ProviderStatusCard", () => {
  it("shows fallback badge for mock providers", () => {
    render(
      <ProviderStatusCard
        provider={{
          name: "mock-llm",
          kind: "llm",
          health: "healthy",
          using_fallback: false,
          is_mock: true,
          detail: "Deterministic mock LLM",
        }}
      />,
    );
    expect(screen.getByText("Mock")).toBeInTheDocument();
    expect(screen.getByText("mock-llm")).toBeInTheDocument();
  });
});

describe("api client types compile", () => {
  it("exports api helpers", async () => {
    const { api } = await import("@/lib/api");
    expect(api.health.get).toBeTypeOf("function");
    expect(api.providers.status).toBeTypeOf("function");
  });
});
