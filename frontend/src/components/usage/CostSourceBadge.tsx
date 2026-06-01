import { cn } from "@/lib/utils";
import type { UsageSummary } from "@/lib/api/types";

export function CostSourceBadge({
  summary,
  costIsPlaceholder,
}: {
  summary: UsageSummary;
  costIsPlaceholder?: boolean;
}) {
  const placeholder = costIsPlaceholder ?? summary.cost_is_placeholder;
  const billingGrade = summary.billing_grade_cost && parseFloat(summary.billing_grade_cost) > 0;

  return (
    <div
      className={cn(
        "rounded-lg border p-4 text-sm",
        placeholder
          ? "border-amber-500/30 bg-amber-500/5 text-amber-100"
          : "border-emerald-500/30 bg-emerald-500/5 text-emerald-100",
      )}
    >
      {billingGrade && !placeholder ? (
        <p>
          Costs include provider-reported amounts ({summary.billing_grade_cost} USD billing-grade).
        </p>
      ) : (
        <p>
          Displayed costs are estimates only — <strong>not billing-grade</strong>. Provider-reported
          billing requires <code className="text-xs">cost_source=provider_reported</code> on usage
          events.
        </p>
      )}
    </div>
  );
}
