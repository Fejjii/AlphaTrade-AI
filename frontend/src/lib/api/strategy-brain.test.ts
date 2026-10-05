import { afterEach, expect, it, vi } from "vitest";
import type { SfpDraft } from "./brain-types";

const apiFetch = vi.fn().mockResolvedValue({});
vi.mock("@/lib/api/client", () => ({ apiFetch: (...args: unknown[]) => apiFetch(...args) }));
afterEach(() => { apiFetch.mockClear(); });
it("sends SFP creation through the existing authenticated template endpoint", async () => {
  const { api } = await import("./index");
  const draft: SfpDraft = {
    symbol: "ETHUSDT", direction: "short", trigger_timeframe: "1w", paper_only: true,
    parameters: { version: "sfp-research/v1", provisional: true, level_lookback: 6, pivot_width: 1, minimum_level_significance: "1", minimum_sweep_depth: "0.002", maximum_sweep_depth: null, equal_level_tolerance: "0.001", reclaim_window: 2, confirmation_window: 3, breakout_confirmation_closes: 2, structural_invalidation_buffer: "0.002", expiry_bars: 12, required_evidence_max_age_bars: 1, quality_lookback: 3, htf_alignment_tolerance: "0.01", confirmation: "closed_break_of_reclaim_extreme" },
  };
  await api.strategyBrain.createSfp(draft);
  expect(apiFetch).toHaveBeenCalledWith("/strategy-brain/templates/sfp", { method: "POST", auth: true, body: JSON.stringify(draft) });
});
