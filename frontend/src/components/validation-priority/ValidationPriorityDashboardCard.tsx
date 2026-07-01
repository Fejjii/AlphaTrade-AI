"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  ValidationPriorityItem,
  ValidationPrioritySummaryResponse,
} from "@/lib/api/types";

import { DASHBOARD_ACTION_LABELS, validationPriorityItemHref } from "./priority-display";

export function ValidationPriorityDashboardCard({
  summary,
  topItems,
}: {
  summary: ValidationPrioritySummaryResponse | null;
  topItems: ValidationPriorityItem[];
}) {
  return (
    <Card data-testid="dashboard-validation-priority">
      <CardHeader>
        <CardTitle className="text-base">Validation Priority</CardTitle>
        <p className="mt-1 text-xs text-zinc-500">
          Read-only study guidance — choose what to validate next. No orders, no automation.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-zinc-300">
        {summary ? (
          <div
            className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"
            data-testid="dashboard-validation-priority-distribution"
          >
            {summary.by_action.map((row) => (
              <div
                key={row.action_label}
                className="rounded border border-zinc-800 px-2 py-1.5"
                data-testid={`dashboard-validation-priority-count-${row.action_label}`}
              >
                <p className="text-lg font-semibold text-zinc-100">{row.count}</p>
                <p className="text-zinc-500">
                  {DASHBOARD_ACTION_LABELS[row.action_label] ?? row.action_label}
                </p>
              </div>
            ))}
          </div>
        ) : null}

        {topItems.length ? (
          <ul className="space-y-2" data-testid="dashboard-validation-priority-top-items">
            {topItems.map((item) => {
              const label = item.condition || item.symbol || item.item_type;
              return (
                <li
                  key={item.item_id}
                  className="rounded border border-zinc-800 px-3 py-2"
                  data-testid={`dashboard-validation-priority-top-${item.item_id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      href={validationPriorityItemHref(item)}
                      className="font-medium text-zinc-100 hover:underline"
                      data-testid={`dashboard-validation-priority-link-${item.item_id}`}
                    >
                      {label}
                    </Link>
                    <span className="text-xs text-zinc-500">score {item.priority_score}</span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">
                    {DASHBOARD_ACTION_LABELS[item.action_label]} · {item.item_type} ·{" "}
                    {item.symbol ?? "—"}
                  </p>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-xs text-zinc-500">
            No pending run plans or candidates to rank yet.
          </p>
        )}

        <Link
          href="/validation-priority"
          className="inline-block text-xs text-zinc-400 underline"
          data-testid="dashboard-validation-priority-view-all"
        >
          Open validation priority
        </Link>
      </CardContent>
    </Card>
  );
}
