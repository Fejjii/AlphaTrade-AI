import type { UsageFeatureBreakdown, UsageProviderBreakdown } from "@/lib/api/types";
import { formatDecimal } from "@/lib/utils";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function UsageFeatureTable({ rows }: { rows: UsageFeatureBreakdown[] }) {
  if (!rows.length) return null;
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
                <td className="py-2">${formatDecimal(row.total_cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export function UsageProviderTable({ rows }: { rows: UsageProviderBreakdown[] }) {
  if (!rows.length) return null;
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
                <td className="py-2 pr-4">${formatDecimal(row.total_cost)}</td>
                <td className="py-2">{row.fallback_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
