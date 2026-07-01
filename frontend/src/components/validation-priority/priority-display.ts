import type { ValidationActionLabel, ValidationPriorityItem } from "@/lib/api/types";

export function validationPriorityItemHref(
  item: Pick<ValidationPriorityItem, "item_type" | "item_id">,
): string {
  if (item.item_type === "run_plan") {
    return `/paper-validation/run-plans/${item.item_id}`;
  }
  return `/paper-validation/candidates/${item.item_id}`;
}

/** Dashboard-safe study guidance labels (no execution wording). */
export const DASHBOARD_ACTION_LABELS: Record<ValidationActionLabel, string> = {
  prioritize: "Validate next",
  watch: "Study next",
  collect_more_data: "Collect more data",
  avoid_for_now: "Avoid for now",
};
