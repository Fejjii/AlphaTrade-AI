import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import JournalPage from "@/app/(app)/journal/page";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: { items: [], total: 0, limit: 50, offset: 0 },
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}));

describe("JournalPage", () => {
  it("renders setup selector and tag fields", () => {
    render(<JournalPage />);
    expect(screen.getByLabelText(/Setup type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Mistake tags/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Emotion tags/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Improvement rule/i)).toBeInTheDocument();
  });
});
