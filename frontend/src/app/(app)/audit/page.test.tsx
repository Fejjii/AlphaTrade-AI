import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AuditPage from "./page";
import type { AuditRecord, PaginatedAuditRecords } from "@/lib/api/types";

function makeEvent(overrides: Partial<AuditRecord> = {}): AuditRecord {
  return {
    event_id: "evt-1",
    request_id: "req-1",
    trace_id: "trace-1",
    user_id: "user-1",
    organization_id: "org-1",
    event_type: "kill_switch.activated",
    resource_type: "kill_switch",
    resource_id: "ks-1",
    actor_type: "user",
    action: "activate",
    result: "success",
    severity: "warning",
    payload_hash: "hash",
    redacted_metadata: {},
    timestamp: "2026-07-27T10:00:00.000Z",
    ...overrides,
  };
}

function paginated(items: AuditRecord[]): PaginatedAuditRecords {
  return { items, total: items.length, limit: 50, offset: 0 };
}

const mockReload = vi.fn();
const mockEvents = vi.fn();

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
      events: (...args: unknown[]) => mockEvents(...args),
    },
  },
}));

describe("AuditPage loading/error honesty", () => {
  beforeEach(() => {
    asyncState = { data: null, loading: true, error: null };
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders only the loading state while the request is unresolved", () => {
    asyncState = { data: null, loading: true, error: null };
    render(<AuditPage />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No audit events/i)).not.toBeInTheDocument();
  });

  it("renders only the error state when the request failed", () => {
    asyncState = { data: null, loading: false, error: "Audit source down" };
    render(<AuditPage />);
    expect(screen.getByTestId("error-state")).toHaveTextContent("Audit source down");
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No audit events/i)).not.toBeInTheDocument();
  });

  it("renders the empty state only after a successful empty response", () => {
    asyncState = { data: paginated([]), loading: false, error: null };
    render(<AuditPage />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent(/No audit events/i);
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
  });

  it("renders audit events after a successful populated response", () => {
    asyncState = {
      data: paginated([
        makeEvent(),
        makeEvent({ event_id: "evt-2", event_type: "risk.settings_updated", severity: "info" }),
      ]),
      loading: false,
      error: null,
    };
    render(<AuditPage />);
    expect(screen.getByText("kill_switch.activated")).toBeInTheDocument();
    expect(screen.getByText("risk.settings_updated")).toBeInTheDocument();
    expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    expect(screen.queryByText(/No audit events/i)).not.toBeInTheDocument();
  });
});
