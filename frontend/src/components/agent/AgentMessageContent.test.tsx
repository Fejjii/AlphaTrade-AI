import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { AgentMessageContent } from "./AgentMessageContent";
afterEach(cleanup);
it("renders one concise response and keeps raw evidence collapsed without a duplicate explanation", () => {
  render(<AgentMessageContent message={{ role: "assistant", content: "BTCUSDT long · BloFin demo. Entry verified; exit unverified.", payload: { interactive_agent: { full_reply: "Duplicate long explanation", recorded_evidence: "command_id=exact-command; historical fill only" } } }} />);
  expect(screen.getByText("BTCUSDT long · BloFin demo. Entry verified; exit unverified.")).toBeVisible();
  const details = screen.getByText("Stored evidence").closest("details");
  expect(details).not.toHaveAttribute("open");
  expect(screen.getByText(/command_id=exact-command/)).not.toBeVisible();
  expect(screen.getByText(/Duplicate long explanation/)).not.toBeVisible();
  expect(screen.queryByText(/Recorded facts/)).not.toBeInTheDocument();
  expect(screen.queryByText(/currently open/i)).not.toBeInTheDocument();
});
it("moves historical appended facts into the collapsed evidence panel", () => {
  render(<AgentMessageContent message={{ role: "assistant", content: "Entry verified.\n\nRecorded facts (not a confirmation):\nRaw identity evidence" }} />);
  expect(screen.getByText("Entry verified.")).toBeVisible();
  expect(screen.getByText("Raw identity evidence")).not.toBeVisible();
});
