import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PaperAccountSetup } from "./PaperAccountSetup";
import { api } from "@/lib/api";
import type { PaperExecutionAccount } from "@/lib/api/types";

const account: PaperExecutionAccount = {
  id: "93ef7157-4a5e-4ae1-a660-3ed93b04ed31", name: "Paper account",
  execution_mode: "PAPER", account_mode: "NET", enabled: true,
};

beforeEach(() => {
  vi.spyOn(api.execution, "paperAccountStatus").mockResolvedValue({ account: null, can_register: true });
  vi.spyOn(api.execution, "registerPaperAccount").mockResolvedValue({ account, created: true });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("Paper account setup", () => {
  it("reads status without registering on mount; explicit setup shows the UUID", async () => {
    render(<PaperAccountSetup />);
    const setup = await screen.findByRole("button", { name: "Set up paper account" });
    expect(api.execution.registerPaperAccount).not.toHaveBeenCalled();
    fireEvent.click(setup);
    expect(await screen.findByText(account.id)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Paper account registered · PAPER / NET");
    expect(api.execution.registerPaperAccount).toHaveBeenCalledExactlyOnceWith();
    expect(screen.queryByRole("button", { name: "Set up paper account" })).not.toBeInTheDocument();
    expect(screen.getByText(/Execution still requires its existing approvals/)).toBeInTheDocument();
  });

  it("shows the existing account UUID without automatic setup", async () => {
    vi.mocked(api.execution.paperAccountStatus).mockResolvedValue({ account, can_register: true });
    render(<PaperAccountSetup />);
    expect(await screen.findByText(account.id)).toBeInTheDocument();
    expect(api.execution.registerPaperAccount).not.toHaveBeenCalled();
  });

  it("requires owner capability from the authenticated API, not the global user role", async () => {
    vi.mocked(api.execution.paperAccountStatus).mockResolvedValue({ account: null, can_register: false });
    render(<PaperAccountSetup />);
    expect(await screen.findByText(/Only an organization owner/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(api.execution.registerPaperAccount).not.toHaveBeenCalled();
  });

  it("shows disabled or ambiguous status errors without offering a reset", async () => {
    vi.mocked(api.execution.paperAccountStatus).mockRejectedValue(new Error("The existing paper account is disabled."));
    render(<PaperAccountSetup />);
    expect(await screen.findByRole("alert")).toHaveTextContent("disabled");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(api.execution.registerPaperAccount).not.toHaveBeenCalled();
  });

  it("reports setup failure without claiming registration succeeded", async () => {
    vi.mocked(api.execution.registerPaperAccount).mockRejectedValue(new Error("Multiple paper accounts require operator review."));
    render(<PaperAccountSetup />);
    fireEvent.click(await screen.findByRole("button", { name: "Set up paper account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("operator review");
    expect(screen.queryByText(account.id)).not.toBeInTheDocument();
  });

  it("keeps setup single flight while awaiting the response and handles account reuse", async () => {
    let resolve!: (result: { account: PaperExecutionAccount; created: boolean }) => void;
    vi.mocked(api.execution.registerPaperAccount).mockImplementation(() => new Promise((done) => { resolve = done; }));
    render(<PaperAccountSetup />);
    const setup = await screen.findByRole("button", { name: "Set up paper account" });
    fireEvent.click(setup);
    fireEvent.click(setup);
    expect(api.execution.registerPaperAccount).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Setting up…" })).toBeDisabled();
    resolve({ account, created: false });
    await waitFor(() => expect(screen.getByText(account.id)).toBeInTheDocument());
  });
});
