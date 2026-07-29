import type { UsageFeatureBreakdown, UsageProviderBreakdown } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type CostTableProps = {
  currencyCode?: string | null;
};

export function UsageFeatureTable({
  rows,
  currencyCode = null,
}: { rows: UsageFeatureBreakdown[] } & CostTableProps) {
  if (!rows.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Usage by feature</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-400">No feature usage yet.</CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Usage by feature</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-500">
            <tr>
              <th className="pb-2 pr-4">Feature</th>
              <th className="pb-2 pr-4">Events</th>
              <th className="pb-2 pr-4">Tokens</th>
              <th className="pb-2">Est. cost</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.feature} className="border-t border-zinc-800">
                <td className="py-2 pr-4">{row.feature}</td>
                <td className="py-2 pr-4">{row.event_count}</td>
                <td className="py-2 pr-4">{row.total_tokens.toLocaleString()}</td>
                <td className="py-2">{formatCurrency(row.total_cost, currencyCode)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export function UsageProviderTable({
  rows,
  currencyCode = null,
}: { rows: UsageProviderBreakdown[] } & CostTableProps) {
  if (!rows.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Usage by provider</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-zinc-400">No provider usage yet.</CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Usage by provider</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-zinc-500">
            <tr>
              <th className="pb-2 pr-4">Provider</th>
              <th className="pb-2 pr-4">Events</th>
              <th className="pb-2 pr-4">Tokens</th>
              <th className="pb-2 pr-4">Est. cost</th>
              <th className="pb-2">Fallbacks</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.provider} className="border-t border-zinc-800">
                <td className="py-2 pr-4">{row.provider}</td>
                <td className="py-2 pr-4">{row.event_count}</td>
                <td className="py-2 pr-4">{row.total_tokens.toLocaleString()}</td>
                <td className="py-2 pr-4">{formatCurrency(row.total_cost, currencyCode)}</td>
                <td className="py-2">{row.fallback_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
