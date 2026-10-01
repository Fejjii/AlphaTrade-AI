import { DataNumber } from "@/components/ui/data-number";
import { UNAVAILABLE } from "@/lib/format";

/** Shared presentation for recorded trading metrics; never supplies a fallback value. */
export function TradingMetric({
  label,
  value,
  note,
  testId,
  amount,
}: {
  label: string;
  value: string;
  note?: string | null;
  testId?: string;
  amount?: string | number | null;
}) {
  const numeric = amount == null || amount === "" ? null : Number(amount);
  const tone =
    value === UNAVAILABLE
      ? "muted"
      : numeric != null && Number.isFinite(numeric) && numeric !== 0
        ? numeric > 0
          ? "positive"
          : "negative"
        : "default";

  return (
    <div
      data-testid={testId}
      className="min-w-0 rounded-control border border-border-subtle bg-surface-0/40 p-3 sm:p-4"
    >
      <p className="text-sm text-text-secondary">{label}</p>
      <DataNumber
        value={value}
        tone={tone}
        className="mt-2 block break-words text-xl font-semibold tracking-tight sm:text-2xl"
      />
      {note ? (
        <p className="mt-2 text-xs leading-relaxed text-text-secondary">
          {note}
        </p>
      ) : null}
    </div>
  );
}
