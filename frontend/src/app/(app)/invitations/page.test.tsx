import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import InvitationsPage from "@/app/(app)/invitations/page";
import type { OrganizationInvitation } from "@/lib/api/types";

const listInvitationsMock = vi.fn();
const createInvitationMock = vi.fn();
const revokeInvitationMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    organizations: {
      listInvitations: (...args: unknown[]) => listInvitationsMock(...args),
      createInvitation: (...args: unknown[]) => createInvitationMock(...args),
      revokeInvitation: (...args: unknown[]) => revokeInvitationMock(...args),
    },
  },
  ApiError: class ApiError extends Error {},
}));

function makeInvitation(
  overrides: Partial<OrganizationInvitation> = {},
): OrganizationInvitation {
  return {
    id: "inv-1",
    organization_id: "org-1",
    email: "trader@example.com",
    role: "trader",
    invited_by_user_id: "user-1",
    expires_at: "2026-08-27T00:00:00.000Z",
    accepted_at: null,
    revoked_at: null,
    created_at: "2026-07-27T00:00:00.000Z",
    is_pending: true,
    ...overrides,
  };
}

describe("InvitationsPage loading/error honesty", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows only the loading state while the list request is unresolved", () => {
    listInvitationsMock.mockReturnValue(new Promise(() => {}));
    render(<InvitationsPage />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByText(/No invitations yet/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
  });

  it("shows only the error state when the list request failed", async () => {
    listInvitationsMock.mockRejectedValue(new Error("boom"));
    render(<InvitationsPage />);
    expect(await screen.findByTestId("error-state")).toHaveTextContent(
      /Could not load invitations/i,
    );
    expect(screen.queryByText(/No invitations yet/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
  });

  it("shows the empty wording only after a successful empty response", async () => {
    listInvitationsMock.mockResolvedValue({ invitations: [] });
    render(<InvitationsPage />);
    expect(await screen.findByText(/No invitations yet/i)).toBeInTheDocument();
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
  });

  it("lists invitations after a successful populated response", async () => {
    listInvitationsMock.mockResolvedValue({
      invitations: [
        makeInvitation(),
        makeInvitation({
          id: "inv-2",
          email: "viewer@example.com",
          role: "viewer",
          is_pending: false,
          accepted_at: "2026-07-28T00:00:00.000Z",
        }),
      ],
    });
    render(<InvitationsPage />);
    expect(await screen.findByText("trader@example.com")).toBeInTheDocument();
    expect(screen.getByText("viewer@example.com")).toBeInTheDocument();
    expect(screen.queryByText(/No invitations yet/i)).not.toBeInTheDocument();
  });

  it("still creates invitations and reloads the list", async () => {
    listInvitationsMock
      .mockResolvedValueOnce({ invitations: [] })
      .mockResolvedValue({ invitations: [makeInvitation()] });
    createInvitationMock.mockResolvedValue(makeInvitation());
    render(<InvitationsPage />);
    await screen.findByText(/No invitations yet/i);

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: "trader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Send invitation/i }));

    await waitFor(() => {
      expect(createInvitationMock).toHaveBeenCalledWith({
        email: "trader@example.com",
        role: "trader",
      });
    });
    expect(await screen.findByText(/Invitation created/i)).toBeInTheDocument();
    expect(await screen.findByText("trader@example.com")).toBeInTheDocument();
    expect(listInvitationsMock).toHaveBeenCalledTimes(2);
  });

  it("still revokes pending invitations and reloads the list", async () => {
    listInvitationsMock
      .mockResolvedValueOnce({ invitations: [makeInvitation()] })
      .mockResolvedValue({ invitations: [] });
    revokeInvitationMock.mockResolvedValue(undefined);
    render(<InvitationsPage />);
    await screen.findByText("trader@example.com");

    fireEvent.click(screen.getByRole("button", { name: /Revoke/i }));

    await waitFor(() => {
      expect(revokeInvitationMock).toHaveBeenCalledWith("inv-1");
    });
    expect(await screen.findByText(/No invitations yet/i)).toBeInTheDocument();
  });
});
