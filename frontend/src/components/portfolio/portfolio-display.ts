import type { PortfolioTrendLabel } from "@/lib/api/types";

export function pnlClassName(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "text-zinc-300";
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num) || num === 0) return "text-zinc-300";
  return num > 0 ? "text-emerald-400" : "text-rose-400";
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function trendLabel(label: PortfolioTrendLabel): string {
  switch (label) {
    case "improving":
      return "Improving";
    case "flat":
      return "Flat";
    case "deteriorating":
      return "Deteriorating";
    default:
      return "Insufficient data";
  }
}

export function trendVariant(
  label: PortfolioTrendLabel,
): "success" | "warning" | "danger" | "muted" {
  switch (label) {
    case "improving":
      return "success";
    case "deteriorating":
      return "danger";
    case "flat":
      return "warning";
    default:
      return "muted";
  }
}

export function sourceLabel(source: string): string {
  switch (source) {
    case "proposal_flow":
      return "Proposal flow";
    case "paper_validation":
      return "Paper validation";
    default:
      return "All sources";
  }
}
