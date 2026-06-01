import { Badge, type BadgeProps } from "@/components/ui/badge";

const toneMap: Record<string, BadgeProps["variant"]> = {
  ok: "success",
  healthy: "success",
  paper: "success",
  pending: "warning",
  degraded: "warning",
  warn: "warning",
  blocked: "danger",
  unavailable: "danger",
  critical: "danger",
  rejected: "danger",
};

export function StatusBadge({
  label,
  tone = "default",
}: {
  label: string;
  tone?: keyof typeof toneMap | "default" | "info" | "muted";
}) {
  const variant =
    tone === "default" || tone === "info" || tone === "muted"
      ? tone
      : (toneMap[tone] ?? "default");
  return <Badge variant={variant}>{label}</Badge>;
}
