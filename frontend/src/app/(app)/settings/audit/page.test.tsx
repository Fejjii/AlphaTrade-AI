import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SettingsAuditPage from "./page";
import type { PaginatedAuditRecords } from "@/lib/api/types";

const mockReload = vi.fn();

let asyncState: {
  data: PaginatedAuditRecords | null;
  loading: boolean;
  error: string | null;
};

vi.mock("@/hooks/useAsyncData", () => ({
  useAsyncData: () => ({
    data: asyncState.data,
    loading: asyncState.loading,
    error: asyncState.error,
    reload: mockReload,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    audit: {
      events: vi.fn(),
    },
  },
}));

describe("Settings audit shim (FP2-129)", () => {
  beforeEach(() => {
    asyncState = {
      data: { items: [], total: 0, limit: 50, offset: 0 },
      loading: false,
      error: null,
    };
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("re-exports the audit page with loading/empty honesty", () => {
    render(<SettingsAuditPage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });

  it("surfaces failed requests without an empty success state", () => {
    asyncState = { data: null, loading: false, error: "Audit unavailable" };
    render(<SettingsAuditPage />);
    expect(screen.getByTestId("error-state")).toHaveTextContent("Audit unavailable");
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
  });
});
