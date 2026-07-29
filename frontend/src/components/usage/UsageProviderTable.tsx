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
        {/* Narrow viewports get a stacked card list so columns are never unreachable. */}
        <ul className="space-y-2 md:hidden" data-testid="usage-feature-cards">
          {rows.map((row) => (
            <li
              key={row.feature}
              className="rounded-control border border-border-subtle px-3 py-2 text-sm"
            >
              <p className="font-medium text-text-primary break-words">{row.feature}</p>
              <p className="mt-1 text-caption text-text-muted">
                Events {row.event_count.toLocaleString()} · Tokens{" "}
                {row.total_tokens.toLocaleString()} · Est. cost{" "}
                {formatCurrency(row.total_cost, currencyCode)}
              </p>
            </li>
          ))}
        </ul>
        <table className="hidden w-full text-left text-sm md:table">
          <caption className="sr-only">Usage by feature</caption>
          <thead className="text-zinc-500">
            <tr>
              <th scope="col" className="pb-2 pr-4">
                Feature
              </th>
              <th scope="col" className="pb-2 pr-4">
                Events
              </th>
              <th scope="col" className="pb-2 pr-4">
                Tokens
              </th>
              <th scope="col" className="pb-2">
                Est. cost
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.feature} className="border-t border-zinc-800">
                <th scope="row" className="max-w-[12rem] break-words py-2 pr-4 font-normal">
                  {row.feature}
                </th>
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
        <ul className="space-y-2 md:hidden" data-testid="usage-provider-cards">
          {rows.map((row) => (
            <li
              key={row.provider}
              className="rounded-control border border-border-subtle px-3 py-2 text-sm"
            >
              <p className="font-medium text-text-primary break-words">{row.provider}</p>
              <p className="mt-1 text-caption text-text-muted">
                Events {row.event_count.toLocaleString()} · Tokens{" "}
                {row.total_tokens.toLocaleString()} · Est. cost{" "}
                {formatCurrency(row.total_cost, currencyCode)} · Fallbacks {row.fallback_count}
              </p>
            </li>
          ))}
        </ul>
        <table className="hidden w-full text-left text-sm md:table">
          <caption className="sr-only">Usage by provider</caption>
          <thead className="text-zinc-500">
            <tr>
              <th scope="col" className="pb-2 pr-4">
                Provider
              </th>
              <th scope="col" className="pb-2 pr-4">
                Events
              </th>
              <th scope="col" className="pb-2 pr-4">
                Tokens
              </th>
              <th scope="col" className="pb-2 pr-4">
                Est. cost
              </th>
              <th scope="col" className="pb-2">
                Fallbacks
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.provider} className="border-t border-zinc-800">
                <th scope="row" className="max-w-[12rem] break-words py-2 pr-4 font-normal">
                  {row.provider}
                </th>
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
