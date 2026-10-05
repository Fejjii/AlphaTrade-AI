import type { SfpParameters } from "@/lib/api/brain-types";

// Reuse the foundation detector's reference configuration, without optimization.
// This is a new-draft convenience only; saved strategy versions are never edited.
export const SFP_RESEARCH_BASELINE: Readonly<SfpParameters> = Object.freeze({
  version: "sfp-research/v1", provisional: true,
  level_lookback: 6, pivot_width: 1, minimum_level_significance: "2",
  minimum_sweep_depth: "0.01", maximum_sweep_depth: "0.05",
  equal_level_tolerance: "0.001", reclaim_window: 2, confirmation_window: 2,
  breakout_confirmation_closes: 2, structural_invalidation_buffer: "0.005",
  expiry_bars: 6, required_evidence_max_age_bars: 1, quality_lookback: 3,
  htf_alignment_tolerance: "0.01", confirmation: "closed_break_of_reclaim_extreme",
});

export const SFP_FIELDS = [
  { key: "level_lookback", label: "Level lookback (bars)", min: 3, max: 1000, integer: true },
  { key: "pivot_width", label: "Pivot width (bars)", min: 1, max: 20, integer: true },
  { key: "minimum_level_significance", label: "Minimum level significance (points)", min: 0 },
  { key: "minimum_sweep_depth", label: "Minimum sweep depth (ratio)", min: 0, max: 1 },
  { key: "maximum_sweep_depth", label: "Maximum sweep depth (optional ratio)", min: 0, max: 1, optional: true },
  { key: "equal_level_tolerance", label: "Equal level tolerance (ratio)", min: 0, max: 1 },
  { key: "reclaim_window", label: "Reclaim window (bars)", min: 0, max: 500, integer: true },
  { key: "confirmation_window", label: "Confirmation window (bars)", min: 1, max: 500, integer: true },
  { key: "breakout_confirmation_closes", label: "Breakout confirmation closes", min: 1, max: 500, integer: true },
  { key: "structural_invalidation_buffer", label: "Structural invalidation buffer (ratio)", min: 0, max: 1 },
  { key: "expiry_bars", label: "Expiry (bars)", min: 1, max: 2000, integer: true },
  { key: "required_evidence_max_age_bars", label: "Required evidence maximum age (bars)", min: 1, max: 10, integer: true },
  { key: "quality_lookback", label: "Quality lookback (bars)", min: 2, max: 500, integer: true },
  { key: "htf_alignment_tolerance", label: "Higher timeframe alignment tolerance (ratio)", min: 0, max: 1 },
] satisfies Array<{
  key: keyof SfpParameters; label: string; min: number; max?: number; integer?: boolean; optional?: boolean;
}>;

export function SfpParameterFields({ disabled }: { disabled: boolean }) {
  return <fieldset disabled={disabled} className="space-y-3">
    <legend className="font-medium">Research baseline preset</legend>
    <p className="text-sm text-text-muted">Provisional reference settings, not validated trading thresholds. Creating a draft does not approve it or enable automatic SFP execution.</p>
    <details className="rounded border border-border p-3">
    <summary className="cursor-pointer font-medium">Advanced parameters</summary>
    <p className="text-sm text-text-muted">All parameters are explicit and provisional. Ratios use 0.01 for 1% and must be below 1. Level lookback must cover both pivot wings. Leave maximum sweep depth blank for no upper bound.</p>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {SFP_FIELDS.map(field => <label key={field.key} className="flex flex-col gap-1 text-sm">
        {field.label}
        <input name={field.key} type="number" required={!("optional" in field && field.optional)}
          defaultValue={SFP_RESEARCH_BASELINE[field.key] ?? ""}
          onInvalid={event => { const advanced = event.currentTarget.closest("details"); if (advanced) advanced.open = true; }}
          min={field.min} max={"max" in field ? field.max : undefined}
          step={"integer" in field && field.integer ? 1 : "any"}
          className="rounded border border-border bg-surface p-2" />
      </label>)}
    </div>
    </details>
    <p className="text-sm">Confirmation requires a closed break of the reclaim extreme. This foundation provides structural research and alerts; it has no authorized SFP execution plan.</p>
  </fieldset>;
}

export function readSfpParameters(form: HTMLFormElement): SfpParameters {
  const data = new FormData(form);
  const values: Record<string, number | string | null> = {};
  for (const field of SFP_FIELDS) {
    const value = String(data.get(field.key) ?? "").trim();
    if (!value && "optional" in field && field.optional) { values[field.key] = null; continue; }
    if (!value) throw new Error(`${field.label} is required`);
    const number = Number(value);
    const integer = "integer" in field && field.integer;
    if (!Number.isFinite(number) || number < field.min || (integer && !Number.isInteger(number)) ||
      ("max" in field && field.max !== undefined && (integer ? number > field.max : number >= field.max))) {
      throw new Error(`${field.label} is outside its supported bounds`);
    }
    // Decimal inputs stay strings so the backend receives the authored precision.
    values[field.key] = integer ? number : value;
  }
  if (Number(values.level_lookback) < 2 * Number(values.pivot_width) + 1) {
    throw new Error("Level lookback must cover both pivot wings");
  }
  if (values.maximum_sweep_depth !== null && Number(values.maximum_sweep_depth) < Number(values.minimum_sweep_depth)) {
    throw new Error("Maximum sweep depth must be at least minimum sweep depth");
  }
  return { ...values, version: "sfp-research/v1", provisional: true, confirmation: "closed_break_of_reclaim_extreme" } as SfpParameters;
}
