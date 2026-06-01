import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/(app)/settings/page";

vi.mock("@/components/PaperModeBanner", () => ({
  PaperModeBanner: () => null,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "owner@example.com", email_verified: true },
    organization: { name: "Alpha Org" },
  }),
}));

vi.mock("@/lib/config", () => ({
  appConfig: {
    apiBaseUrl: "http://localhost:8000",
    executionMode: "paper",
    providerMode: "mock",
  },
}));

describe("SettingsPage", () => {
  it("shows email verification status", () => {
    render(<SettingsPage />);
    expect(screen.getByText(/Email verified/i)).toBeInTheDocument();
    expect(screen.getByText(/Yes/)).toBeInTheDocument();
  });
});
