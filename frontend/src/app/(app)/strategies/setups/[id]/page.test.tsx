import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { BrainSetup } from "@/lib/api/brain-types";
import BrainSetupPage from "./page";

const mocks = vi.hoisted(() => ({ setup: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { strategyBrain: mocks } }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "sfp-setup" }) }));
const setup: BrainSetup = { setup_id: "sfp-setup", strategy_version_id: "sfp-version", family: "sfp", timeframe: "4h", instrument: "BTCUSDT", direction: "long", condition: "confirmed_sfp", state: "CONFIRMED", observed_at: "2026-10-01T00:00:00Z", expires_at: "2026-10-10T00:00:00Z", fresh_until: "2026-10-10T00:00:00Z", freshness: "AVAILABLE", risk_state: "not_evaluated", reason_codes: [], evidence_reference: "hash", evidence: {}, candidate_id: null, decision_id: null, journal: null, quality_components: {}, entry: null, stop: null, targets: [] };
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it("shows the SFP condition, bound timeframe and research scope in stored details", async () => {
  mocks.setup.mockResolvedValue(setup);
  render(<BrainSetupPage />);
  expect(await screen.findByRole("heading", { name: "SFP confirmed_sfp · CONFIRMED" })).toBeInTheDocument();
  expect(screen.getByText(/BTCUSDT · long · 4h · evidence/)).toBeInTheDocument();
  expect(screen.getByText("Strategy version sfp-version")).toBeInTheDocument();
  expect(screen.getByText(/No SFP execution plan is authorized/)).toBeInTheDocument();
  expect(screen.queryByText(/Entry concept/)).toBeNull();
});
