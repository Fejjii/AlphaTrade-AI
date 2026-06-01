import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProviderStatusCard } from "@/components/ProviderStatusCard";
import type { ProviderStatus } from "@/lib/api/types";

const mockProvider: ProviderStatus = {
  name: "mock-llm",
  kind: "llm",
  health: "healthy",
  using_fallback: false,
  is_mock: true,
  detail: "Deterministic offline LLM",
};

const liveProvider: ProviderStatus = {
  name: "openai-llm",
  kind: "llm",
  health: "healthy",
  using_fallback: true,
  is_mock: false,
  detail: "Using mock fallback",
  error_message: "OpenAI unreachable",
};

describe("ProviderStatusCard", () => {
  it("renders mock provider badge", () => {
    render(<ProviderStatusCard provider={mockProvider} />);
    expect(screen.getByText("mock-llm")).toBeInTheDocument();
    expect(screen.getByText("Mock")).toBeInTheDocument();
  });

  it("renders fallback and error for degraded provider", () => {
    render(<ProviderStatusCard provider={liveProvider} />);
    expect(screen.getByText("Fallback")).toBeInTheDocument();
    expect(screen.getByText(/OpenAI unreachable/)).toBeInTheDocument();
  });
});
