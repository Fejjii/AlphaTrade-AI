import { Badge } from "@/components/ui/badge";

export function ConfidenceBadge({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) {
    return <Badge variant="muted">Confidence —</Badge>;
  }
  const pct = Math.round(value * 100);
  const variant = pct >= 75 ? "success" : pct >= 50 ? "warning" : "danger";
  return <Badge variant={variant}>{pct}% confidence</Badge>;
}
