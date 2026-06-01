import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import InvitationsPage from "@/app/(app)/invitations/page";

vi.mock("@/lib/api", () => ({
  api: {
    organizations: {
      listInvitations: vi.fn().mockResolvedValue({ invitations: [] }),
      createInvitation: vi.fn(),
      revokeInvitation: vi.fn(),
    },
  },
  ApiError: class ApiError extends Error {},
}));

describe("InvitationsPage", () => {
  it("compiles and renders invitations UI", async () => {
    render(<InvitationsPage />);
    expect(screen.getByRole("heading", { name: /Team invitations/i })).toBeInTheDocument();
    expect(await screen.findByText(/No invitations yet/i)).toBeInTheDocument();
  });
});
