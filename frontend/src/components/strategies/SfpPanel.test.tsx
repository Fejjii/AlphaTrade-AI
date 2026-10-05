import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BrainOverview, BrainStrategy, SfpParameters } from "@/lib/api/brain-types";
import { NestedContinuationPanel } from "./NestedContinuationPanel";
import { SfpPanel } from "./SfpPanel";
import { SFP_RESEARCH_BASELINE } from "./SfpParameterFields";

const mocks = vi.hoisted(() => ({ overview: vi.fn(), createNested: vi.fn(), createSfp: vi.fn(), compileVersion: vi.fn(), approveVersion: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { strategyBrain: mocks, strategies: mocks } }));
const parameters: SfpParameters = {
  version: "sfp-research/v1", provisional: true,
  level_lookback: 6, pivot_width: 1, minimum_level_significance: "1",
  minimum_sweep_depth: "0.002000000000000001", maximum_sweep_depth: null,
  equal_level_tolerance: "0.001", reclaim_window: 2, confirmation_window: 3,
  breakout_confirmation_closes: 2, structural_invalidation_buffer: "0.002",
  expiry_bars: 12, required_evidence_max_age_bars: 1, quality_lookback: 3,
  htf_alignment_tolerance: "0.01", confirmation: "closed_break_of_reclaim_extreme",
};
const sfp: BrainStrategy = {
  strategy_id: "sfp-id", version_id: "sfp-version", version: 2, name: "SFP BTCUSDT 4h",
  status: "draft", enabled: true, execution_permission: "none",
  spec: { kind: "swing_failure_pattern/v1", symbol: "BTCUSDT", direction: "long", trigger_timeframe: "4h", parameters: { ...parameters } },
};
const nested: BrainStrategy = { ...sfp, strategy_id: "nested-id", version_id: "nested-version", name: "Nested BTCUSDT 15m", spec: { ...sfp.spec, kind: "operational_nested_continuation/v1", trigger_timeframe: "15m" } };
const overview = (strategies: BrainStrategy[] = []): BrainOverview => ({ watched_symbols: ["BTCUSDT", "ETHUSDT"], strategies, setups: [], limitations: [], paper_only: true });
function authorParameters() {
  const form = screen.getByRole("form", { name: "SFP research draft" });
  for (const [name, value] of Object.entries(parameters)) {
    const input = form.querySelector(`input[name="${name}"]`);
    if (input) fireEvent.change(input, { target: { value: value ?? "" } });
  }
  return form;
}
afterEach(() => { cleanup(); vi.resetAllMocks(); });
describe("SFP creation and immutable approval", () => {
  it("creates a provisional baseline draft with advanced parameters collapsed and no approval", async () => {
    mocks.overview.mockResolvedValue(overview());
    mocks.createSfp.mockResolvedValue({ strategy_id: "sfp-id", version_id: "sfp-version" });
    render(<SfpPanel />);
    const create = await screen.findByText("Create SFP research draft");
    expect(screen.getByText("Advanced parameters").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText(/not validated trading thresholds/)).toBeInTheDocument();
    fireEvent.click(create);
    await act(async () => {});
    expect(mocks.createSfp).toHaveBeenCalledWith({ symbol: "BTCUSDT", direction: "long", trigger_timeframe: "15m", parameters: SFP_RESEARCH_BASELINE, paper_only: true });
    expect(mocks.compileVersion).not.toHaveBeenCalled();
    expect(mocks.approveVersion).not.toHaveBeenCalled();
  });
  it("submits explicitly authored parameters, preserves decimal precision and never auto-approves", async () => {
    mocks.overview.mockResolvedValue(overview());
    mocks.createSfp.mockResolvedValue({ strategy_id: "sfp-id", version_id: "sfp-version" });
    render(<SfpPanel />);
    await screen.findByText("Create SFP research draft");
    expect(screen.getByLabelText("Level lookback (bars)")).toHaveValue(SFP_RESEARCH_BASELINE.level_lookback);
    fireEvent.change(screen.getByLabelText("SFP market"), { target: { value: "ETHUSDT" } });
    fireEvent.change(screen.getByLabelText("SFP direction"), { target: { value: "short" } });
    fireEvent.change(screen.getByLabelText("SFP timeframe"), { target: { value: "4h" } });
    authorParameters();
    fireEvent.click(screen.getByText("Create SFP research draft"));
    await act(async () => {});
    expect(mocks.createSfp).toHaveBeenCalledWith({ symbol: "ETHUSDT", direction: "short", trigger_timeframe: "4h", parameters, paper_only: true });
    expect(mocks.createNested).not.toHaveBeenCalled();
    expect(mocks.compileVersion).not.toHaveBeenCalled();
    expect(mocks.approveVersion).not.toHaveBeenCalled();
  });
  it("compiles then approves only the reviewed SFP immutable version", async () => {
    mocks.overview.mockResolvedValue(overview([nested, sfp]));
    mocks.compileVersion.mockResolvedValue({ status: "executable", failures: [] });
    mocks.approveVersion.mockResolvedValue({});
    render(<SfpPanel />);
    fireEvent.click(await screen.findByText("Approve these research rules"));
    await act(async () => {});
    expect(mocks.compileVersion).toHaveBeenCalledWith("sfp-id", "sfp-version");
    expect(mocks.approveVersion).toHaveBeenCalledWith("sfp-id", "sfp-version", { confirm: "I confirm" });
    expect(mocks.compileVersion.mock.invocationCallOrder[0]).toBeLessThan(mocks.approveVersion.mock.invocationCallOrder[0]);
    expect(screen.getByText(/No SFP entry, stop, target or execution plan is authorized/)).toBeInTheDocument();
    expect(screen.queryByText(/Nested BTCUSDT 15m/)).toBeNull();
  });
  it.each(["compile", "approval", "creation"])("surfaces %s failures and keeps approval gated", async (phase) => {
    mocks.overview.mockResolvedValue(overview([sfp]));
    mocks.compileVersion.mockResolvedValue({ status: phase === "compile" ? "invalid" : "executable", failures: [{ message: "Review required" }] });
    mocks.approveVersion.mockRejectedValue(new Error("Approval rejected"));
    mocks.createSfp.mockRejectedValue(new Error("Creation rejected"));
    render(<SfpPanel />);
    await screen.findByText("Approve these research rules");
    if (phase === "creation") { authorParameters(); fireEvent.click(screen.getByText("Create SFP research draft")); }
    else fireEvent.click(screen.getByText("Approve these research rules"));
    expect(await screen.findByRole("alert")).toHaveTextContent(phase === "compile" ? "Review required" : `${phase === "approval" ? "Approval" : "Creation"} rejected`);
    if (phase !== "approval") expect(mocks.approveVersion).not.toHaveBeenCalled();
  });
  it("rejects incompatible authored parameters before acquisition", async () => {
    mocks.overview.mockResolvedValue(overview());
    render(<SfpPanel />);
    await screen.findByText("Create SFP research draft");
    authorParameters();
    fireEvent.change(screen.getByLabelText("Pivot width (bars)"), { target: { value: "4" } });
    fireEvent.click(screen.getByText("Create SFP research draft"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Level lookback must cover both pivot wings");
    expect(mocks.createSfp).not.toHaveBeenCalled();
  });
  it("keeps SFP versions and lifecycle facts out of the Nested view", async () => {
    mocks.overview.mockResolvedValue({ ...overview([nested, sfp]), setups: [{ setup_id: "sfp-setup", strategy_version_id: "sfp-version", family: "sfp", timeframe: "4h", instrument: "BTCUSDT", direction: "long", condition: "confirmed_sfp", state: "CONFIRMED", observed_at: "2026-10-01T00:00:00Z", expires_at: "2026-10-10T00:00:00Z", fresh_until: "2026-10-10T00:00:00Z", freshness: "AVAILABLE", risk_state: "not_evaluated", reason_codes: [], evidence_reference: "hash", evidence: {}, candidate_id: null, decision_id: null, journal: null, quality_components: {}, entry: null, stop: null, targets: [] }] });
    render(<NestedContinuationPanel />);
    expect(await screen.findByText(/Nested BTCUSDT 15m/)).toBeInTheDocument();
    expect(screen.queryByText(/SFP BTCUSDT 4h/)).toBeNull();
    expect(screen.queryByText(/confirmed_sfp/)).toBeNull();
  });
});
