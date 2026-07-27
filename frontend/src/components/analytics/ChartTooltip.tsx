import type { TooltipProps } from "recharts";

type ChartTooltipEntry = {
  name?: string;
  value?: number | string;
  color?: string;
};

/** Dark-theme-compatible Recharts tooltip — signed monetary values, no currency symbols. */
export function ChartTooltip({
  active,
  payload,
  label,
  labelPrefix = "",
}: TooltipProps<number, string> & { labelPrefix?: string }) {
  if (!active || !payload?.length) return null;

  return (
    <div
      className="rounded-control border border-border-subtle bg-surface-2 px-3 py-2 text-xs text-text-primary shadow-elevation2"
      data-testid="chart-tooltip"
    >
      <p className="mb-1 font-medium text-text-secondary">
        {labelPrefix}
        {label != null ? String(label) : ""}
      </p>
      <ul className="space-y-0.5">
        {(payload as ChartTooltipEntry[]).map((entry) => (
          <li key={String(entry.name)} className="font-data text-text-primary">
            {entry.name}: {entry.value}
          </li>
        ))}
      </ul>
    </div>
  );
}
