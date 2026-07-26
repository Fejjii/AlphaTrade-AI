import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AttentionQueue } from "@/components/workflows/AttentionQueue";
import type { AttentionItemModel } from "@/components/workflows/types";

afterEach(cleanup);

const sampleItems: AttentionItemModel[] = [
  {
    id: "pending-approvals",
    section: "pending_decisions",
    priority: 2,
    title: "Approvals awaiting your decision",
    summary: "2 paper approvals pending.",
    href: "/approvals",
    actionLabel: "Review approvals",
    count: 2,
  },
  {
    id: "pending-lessons",
    section: "lessons",
    priority: 6,
    title: "Lessons awaiting review",
    summary: "1 lesson pending.",
    href: "/lessons",
    actionLabel: "Review lessons",
    count: 1,
  },
];

describe("AttentionQueue", () => {
  it("renders prioritized sections and deep links", () => {
    render(<AttentionQueue items={sampleItems} />);
    expect(screen.getByRole("heading", { name: /what needs my attention/i })).toBeInTheDocument();
    expect(screen.getByTestId("attention-section-pending_decisions")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review approvals/i })).toHaveAttribute(
      "href",
      "/approvals",
    );
    expect(screen.getByRole("link", { name: /review lessons/i })).toHaveAttribute(
      "href",
      "/lessons",
    );
  });

  it("shows empty, loading, and error states honestly", () => {
    const { rerender } = render(<AttentionQueue items={[]} loading />);
    expect(screen.getByText(/loading attention queue/i)).toBeInTheDocument();

    rerender(<AttentionQueue items={[]} error="Boom" onRetry={() => undefined} />);
    expect(screen.getByText(/attention queue unavailable/i)).toBeInTheDocument();
    expect(screen.getByText("Boom")).toBeInTheDocument();

    rerender(<AttentionQueue items={[]} />);
    expect(screen.getByText(/nothing needs your attention/i)).toBeInTheDocument();
  });

  it("uses a single-column list structure suitable for mobile", () => {
    const { container } = render(<AttentionQueue items={sampleItems} />);
    expect(container.querySelector("[data-testid='attention-queue']")).toBeTruthy();
    expect(container.querySelectorAll("ul").length).toBeGreaterThan(0);
    expect(container.querySelector(".grid-cols-2")).toBeNull();
  });
});
