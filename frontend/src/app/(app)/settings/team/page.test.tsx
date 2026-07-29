import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SettingsTeamPage from "./page";

const listInvitationsMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    organizations: {
      listInvitations: (...args: unknown[]) => listInvitationsMock(...args),
      createInvitation: vi.fn(),
      revokeInvitation: vi.fn(),
    },
  },
  ApiError: class ApiError extends Error {},
}));

describe("Settings team shim (FP2-129)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("re-exports invitations with honest empty state after success", async () => {
    listInvitationsMock.mockResolvedValue({ invitations: [] });
    render(<SettingsTeamPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Team invitations/i);
    expect(await screen.findByText(/No invitations yet/i)).toBeInTheDocument();
    expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
  });

  it("does not fabricate an empty success while loading", () => {
    listInvitationsMock.mockReturnValue(new Promise(() => {}));
    render(<SettingsTeamPage />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.queryByText(/No invitations yet/i)).not.toBeInTheDocument();
  });
});
