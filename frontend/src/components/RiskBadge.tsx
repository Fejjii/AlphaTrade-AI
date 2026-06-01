import { Badge } from "@/components/ui/badge";
import type { RiskSeverity } from "@/lib/api/types";

const variantMap: Record<RiskSeverity, "info" | "success" | "warning" | "danger"> = {
  info: "info",
  low: "success",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

export function RiskBadge({ level }: { level: RiskSeverity | string | null | undefined }) {
  if (!level) return <Badge variant="muted">Risk unknown</Badge>;
  const normalized = level.toLowerCase() as RiskSeverity;
  return <Badge variant={variantMap[normalized] ?? "default"}>Risk {level}</Badge>;
}
