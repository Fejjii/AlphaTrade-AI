import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NestedContinuationPanel } from "./NestedContinuationPanel";
import type { BrainOverview } from "@/lib/api/brain-types";

const mocks = vi.hoisted(() => ({ overview: vi.fn(), createNested: vi.fn(), compileVersion: vi.fn(), approveVersion: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { strategyBrain: mocks, strategies: mocks } }));
const snapshot = (): BrainOverview => ({
  watched_symbols: ["BTCUSDT", "ETHUSDT"], strategies: [], limitations: [], paper_only: true,
  setups: [{ setup_id: "episode", strategy_version_id: "v1", state: "FORMING", instrument: "BTCUSDT", direction: "long", stage: "N2", observed_at: "2026-10-01T00:00:00Z", fresh_until: "2026-10-01T00:00:10Z", expires_at: "2026-10-01T00:00:20Z", freshness: "AVAILABLE", risk_state: "not_evaluated", reason_codes: ["awaiting_closed_structural_break"], evidence_reference: "hash", evidence: { cvd: "UNSUPPORTED" }, candidate_id: null, decision_id: null, journal: null, quality_components: {}, entry: "100", stop: "98", targets: ["106"] }],
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks(); });
describe("Nested Continuation stored setup view", () => {
  it("expires evidence and the setup while a refresh remains unresolved", async () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-01T00:00:00Z"));
    mocks.overview.mockResolvedValueOnce(snapshot()).mockReturnValue(new Promise(() => {}));
    render(<NestedContinuationPanel />);
    await act(async () => {});
    expect(screen.getByText(/BTCUSDT · N2 · FORMING/)).toBeTruthy();
    expect(screen.getByText(/evidence AVAILABLE/)).toBeTruthy();
    fireEvent.click(screen.getByText("Refresh stored setups"));
    await act(async () => { vi.advanceTimersByTime(10_001); });
    expect(screen.getByText(/evidence STALE/)).toBeTruthy();
    await act(async () => { vi.advanceTimersByTime(10_000); });
    expect(screen.getByText(/BTCUSDT · N2 · EXPIRED/)).toBeTruthy();
    expect(mocks.overview).toHaveBeenCalledTimes(2);
  });
  it("creates only an explicit configured-market research draft", async () => {
    mocks.overview.mockResolvedValue({ ...snapshot(), setups: [] });
    mocks.createNested.mockResolvedValue({});
    render(<NestedContinuationPanel />);
    await screen.findByText("Create research draft");
    fireEvent.change(screen.getByLabelText("Nested market"), { target: { value: "ETHUSDT" } });
    fireEvent.change(screen.getByLabelText("Nested direction"), { target: { value: "short" } });
    fireEvent.click(screen.getByText("Create research draft"));
    await act(async () => {});
    expect(mocks.createNested).toHaveBeenCalledWith({symbol: "ETHUSDT", direction: "short", trigger_timeframe: "15m"});
    expect(mocks.approveVersion).not.toHaveBeenCalled();
  });
  it("shows honest failures instead of invented setup state", async () => {
    mocks.overview.mockRejectedValue(new Error("Stored evidence unavailable"));
    render(<NestedContinuationPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Stored evidence unavailable");
    expect(screen.queryByText(/N2/)).toBeNull();
  });
});
