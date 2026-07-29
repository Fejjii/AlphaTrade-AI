import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AuditEventCard } from "@/components/AuditEventCard";
import type { AuditRecord } from "@/lib/api/types";

afterEach(cleanup);

function makeEvent(overrides: Partial<AuditRecord> = {}): AuditRecord {
  return {
    event_id: "evt-1",
    request_id: "req-very-long-request-identifier-0123456789abcdef",
    trace_id: "trace-1",
    user_id: "user-1",
    organization_id: "org-1",
    event_type: "kill_switch.activated",
    resource_type: "kill_switch",
    resource_id: "resource-uuid-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    actor_type: "user",
    action: "activate",
    result: "success",
    severity: "warning",
    payload_hash: "hash",
    redacted_metadata: {
      detail: "nested-payload-value-that-must-remain-readable-on-narrow-viewports",
    },
    timestamp: "2026-07-27T10:00:00.000Z",
    ...overrides,
  };
}

describe("AuditEventCard mobile readability", () => {
  it("keeps long identifiers and payloads wrappable at narrow widths", () => {
    render(<AuditEventCard event={makeEvent()} />);

    const identifiers = screen.getByTestId("audit-event-identifiers");
    expect(identifiers.className).toMatch(/min-w-0/);

    const request = screen.getByTestId("audit-event-request-id");
    const resource = screen.getByTestId("audit-event-resource-id");
    expect(request.className).toMatch(/break-all/);
    expect(resource.className).toMatch(/break-all/);
    expect(request).toHaveTextContent(
      "req-very-long-request-identifier-0123456789abcdef",
    );
    expect(resource).toHaveTextContent(
      "resource-uuid-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    );

    const metadata = screen.getByTestId("audit-event-metadata");
    expect(metadata.className).toMatch(/overflow-x-auto/);
    expect(metadata.className).toMatch(/break-all/);
  });
});
